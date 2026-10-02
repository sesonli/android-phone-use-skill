"""Replay synthetic Android UI frames through the real capture algorithms.

Only device transport and time are replaced. No phone or private UI data is used.
"""
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import base64
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1]/'skills/android-phone-use/scripts'
runtime_spec = importlib.util.spec_from_file_location('capture_test_runtime', SCRIPTS/'runtime.py')
runtime = importlib.util.module_from_spec(runtime_spec)
runtime_spec.loader.exec_module(runtime)
spec = importlib.util.spec_from_file_location('capture_under_test', SCRIPTS/'phoneuse.py')
capture = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'runtime': runtime}), \
     patch.object(runtime, 'configure_adb', return_value=Path(sys.executable)), \
     patch.object(runtime, 'add_vendor'):
    spec.loader.exec_module(capture)

PACKAGE = 'org.example.synthetic'
RECORD = PACKAGE+':id/record'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII=')


def frame(labels, positions=None):
    root = ET.Element('hierarchy')
    screen = ET.SubElement(root, 'node', {'bounds': '[0,0][400,800]',
                                         'package': PACKAGE, 'class': 'android.widget.FrameLayout'})
    for index, label in enumerate(labels):
        y = positions[index] if positions else 50+100*index
        wrapper = ET.SubElement(screen, 'node', {'resource-id': RECORD,
                'bounds': f'[0,{y}][400,{y+90}]', 'class': 'android.widget.LinearLayout'})
        ET.SubElement(wrapper, 'node', {'resource-id': PACKAGE+':id/title', 'text': label,
                'bounds': f'[10,{y+10}][390,{y+40}]', 'visible-to-user': 'true'})
        ET.SubElement(wrapper, 'node', {'resource-id': PACKAGE+':id/subtitle',
                'content-desc': '说明 & detail', 'bounds': f'[10,{y+40}][390,{y+70}]'})
    return ET.tostring(root, encoding='unicode')


class Clock:
    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds


class Device:
    def __init__(self, frames, packages=None):
        self.frames = frames
        self.index = 0
        self.packages = iter(packages or [PACKAGE]*20)
        self.swipes = 0
        self.read_options = []

    @property
    def info(self):
        return {'currentPackageName': next(self.packages)}

    def app_current(self):
        return {'package': PACKAGE}

    def dump_hierarchy(self, **kwargs):
        self.read_options.append(kwargs)
        return self.frames[self.index]

    def adb(self, serial, *arguments):
        if arguments[:3] == ('shell', 'input', 'swipe'):
            self.swipes += 1
            self.index = min(self.index+1, len(self.frames)-1)
            return b''
        if arguments == ('exec-out', 'screencap', '-p'):
            return PNG
        raise AssertionError(f'Unexpected transport operation: {arguments}')


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/'scan.json'
        self.clock = Clock()

    def args(self, **changes):
        values = dict(serial='SYNTHETIC_DEVICE', backend='u2', profile='stable',
            package=PACKAGE, record_id=RECORD, region=[0,0,400,600],
            swipe=[200,550,200,250,300], pages=20, max_records=None,
            wait_seconds=0.15, stable_seconds=0.02, poll_seconds=0.01,
            settle_seconds=0.01, min_overlap=2, screenshots='all',
            sparse_threshold=8, output=self.output)
        values.update(changes)
        return SimpleNamespace(**values)

    def environment(self, device):
        stack = ExitStack()
        stack.enter_context(patch.object(capture, 'service', return_value=device))
        stack.enter_context(patch.object(capture, 'adb', side_effect=device.adb))
        stack.enter_context(patch.object(capture.time, 'perf_counter', side_effect=lambda: self.clock.now))
        stack.enter_context(patch.object(capture.time, 'sleep', side_effect=self.clock.sleep))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_nested_unicode_fields_and_accessibility_description(self):
        tree = capture.parse_tree(frame(['记录一']))
        self.assertEqual([x['text'] for x in tree['labels']], ['记录一', '说明 & detail'])
        self.assertEqual(tree['screen'], [400,800])
        title, description = tree['labels']
        self.assertEqual(tree['nodes'][title['node']]['parent'], tree['nodes'][description['node']]['parent'])

    def test_snapshot_preserves_unicode_and_lossless_png(self):
        device = Device([frame(['语音转写测试'])])
        with self.environment(device):
            capture.snapshot(self.args(screenshot=True))
        result = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(result['tree']['labels'][0]['text'], '语音转写测试')
        self.assertEqual(self.output.with_suffix('.png').read_bytes(), PNG)

    def test_ordered_scan_limit_deduplication_and_extra_raw_records(self):
        device = Device([frame(['一','二','三','四']), frame(['三','四','五','六','额外'])])
        with self.environment(device):
            capture.scan(self.args(max_records=6))
        result = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual([r['labels'][0] for r in result['records']], ['一','二','三','四','五','六'])
        self.assertEqual([r['first_page'] for r in result['records']], [1,1,1,1,2,2])
        self.assertEqual(result['unique_records'], 6)
        self.assertEqual(result['pages_captured'], 2)
        self.assertEqual(result['pages'][0]['overlap_records'], 2)
        self.assertIn('额外', [x['text'] for x in result['pages'][1]['tree']['labels']])
        for index in (1,2):
            self.assertEqual((self.output.parent/f'page-{index}.png').read_bytes(), PNG)
        self.assertTrue(all(options['root_in_active'] for options in device.read_options))
        self.assertEqual(device.swipes, 1)

    def test_clipped_record_is_excluded_but_raw_tree_retained(self):
        device = Device([frame(['完整','截断'], positions=[50,590])])
        with self.environment(device):
            capture.scan(self.args(pages=1))
        result = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual([r['labels'][0] for r in result['records']], ['完整'])
        self.assertIn('截断', [x['text'] for x in result['pages'][0]['tree']['labels']])
        self.assertEqual(device.swipes, 0)

    def test_inadequate_overlap_stops_and_keeps_failure_evidence(self):
        device = Device([frame(['一','二','三','四']), frame(['四','五','六'])])
        with self.environment(device), self.assertRaisesRegex(RuntimeError, 'continuity lost'):
            capture.scan(self.args())
        failure = json.loads((self.output.parent/'continuity-failure.json').read_text(encoding='utf-8'))
        self.assertEqual(failure['overlap'], 1)
        self.assertEqual(len(failure['accepted_pages']), 1)
        self.assertIn('六', [x['text'] for x in failure['next_tree']['labels']])
        self.assertEqual(device.swipes, 1)
        self.assertFalse(self.output.exists())

    def test_common_records_in_wrong_order_do_not_establish_continuity(self):
        device = Device([frame(['一','二','三','四']), frame(['三','二','五'])])
        with self.environment(device), self.assertRaisesRegex(RuntimeError, 'overlap 0'):
            capture.scan(self.args())
        self.assertEqual(device.swipes, 1)

    def test_wrong_foreground_package_blocks_capture_and_scroll(self):
        device = Device([frame(['一','二'])], packages=['org.example.other'])
        with self.environment(device), self.assertRaisesRegex(RuntimeError, 'expected'):
            capture.scan(self.args())
        self.assertEqual(device.swipes, 0)
        self.assertFalse(self.output.exists())

    def test_app_change_blocks_next_scroll(self):
        device = Device([frame(['一','二'])], packages=[PACKAGE,'org.example.other'])
        with self.environment(device), self.assertRaisesRegex(RuntimeError, 'Foreground app changed'):
            capture.scan(self.args())
        self.assertEqual(device.swipes, 0)

    def test_unchanged_list_stops_instead_of_repeating_twenty_pages(self):
        device = Device([frame(['一','二'])])
        with self.environment(device):
            capture.scan(self.args())
        result = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(result['pages_captured'], 1)
        self.assertEqual(result['pages'][0]['stop_reason'], 'No new accessible text after scroll')
        self.assertFalse(result['pages'][0]['stability']['changed'])
        self.assertEqual(device.swipes, 1)

    def test_empty_selected_records_fail_without_scrolling(self):
        device = Device([frame([])])
        with self.environment(device), self.assertRaisesRegex(RuntimeError, 'did not become stable'):
            capture.scan(self.args())
        self.assertEqual(device.swipes, 0)

    def test_changing_bounds_are_not_accepted_at_timeout(self):
        reads = 0
        def read():
            nonlocal reads
            reads += 1
            return {'state': [('record', (0,reads % 2,100,50))]}, 0.0, 0.0
        with self.environment(Device([])), self.assertRaisesRegex(RuntimeError, 'did not become stable'):
            capture.wait_stable(read, lambda tree: tree['state'], None, 0.15, 0.03, 0.01)
        self.assertGreaterEqual(reads, 10)

    def test_png_capture_rejects_other_formats_without_writing(self):
        output = self.output.with_suffix('.png')
        with patch.object(capture, 'adb', return_value=b'JPEG'), self.assertRaisesRegex(RuntimeError, 'did not return PNG'):
            capture.screenshot('SYNTHETIC_DEVICE', output)
        self.assertFalse(output.exists())

    def test_toolkit_doctor_checks_current_runtime_dependency_directory(self):
        vendor = self.output.parent/'isolated-vendor'
        (vendor/'uiautomator2').mkdir(parents=True)
        out = io.StringIO()
        with patch.object(capture, 'checked_device'), \
             patch.object(runtime, 'vendor_dir', return_value=vendor), \
             patch.dict(sys.modules, {'runtime': runtime}), \
             patch.object(sys, 'argv', ['phoneuse.py','--serial','SYNTHETIC_DEVICE','doctor']), \
             redirect_stdout(out):
            # Resolve through the runtime module to detect a stale hard-coded path.
            capture.main()
        self.assertTrue(json.loads(out.getvalue())['vendor_uiautomator2'])


if __name__ == '__main__':
    unittest.main()
