"""Actual raster/crop tests and provenance checks; no claims of visual acceptance."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SINGLE = Path(__file__).resolve().parents[3] / 'product-single-image-generator/scripts'
sys.path.insert(0, str(SINGLE))
from PIL import Image, ImageDraw, PngImagePlugin
from finalize_a_plus_image import TARGET, METHOD, METADATA_KEY, CROP_REVIEW, assess_crop, crop_geometry, finalize, export_errors
from quality_rules import review_binding



from project_store import read_json as store_read, write_json as store_write, read_bytes as store_bytes, exists as store_exists

class CodeCropTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='code-crop-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw, self.out = self.root / 'raw.png', self.root / 'final.png'
        image = Image.new('RGB', (1536, 1024), '#e6d9c6')
        draw = ImageDraw.Draw(image)
        draw.rectangle((200, 350, 800, 650), fill='#c02030')
        draw.text((900, 480), 'FEATURE', fill='black')
        image.save(self.raw)
        self.requirements = {'postprocess': METHOD, 'width_px': 1464, 'height_px': 600, 'format': 'PNG'}

    def test_real_pixels_crop_preserves_required_region_and_original(self):
        original = store_bytes(self.raw)
        record = finalize(self.raw, self.out, [.1, .25, .95, .75])
        self.assertEqual(store_bytes(self.raw), original)
        with Image.open(self.out) as image:
            self.assertEqual(image.size, TARGET)
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(json.loads(image.info[METADATA_KEY]), record)
            self.assertEqual(image.convert('RGB').getpixel((400, 300)), (192, 32, 48))
        x0, y0, x1, y1 = record['crop_box']
        self.assertLessEqual(x0, .1 * 1536)
        self.assertLessEqual(y0, .25 * 1024)
        self.assertGreaterEqual(x1, .95 * 1536)
        self.assertGreaterEqual(y1, .75 * 1024)
        self.assertAlmostEqual((x1-x0)/(y1-y0), 1464/600)
        self.assertEqual(export_errors(self.root, self.out, self.requirements), [])

    def test_crop_follows_required_content_instead_of_always_centering(self):
        box = crop_geometry((1536, 1024), [.1, .01, .9, .5])
        self.assertEqual(box[1], 0)
        self.assertLess(box[3], 700)

    def test_matching_ratio_downscales_full_frame_without_distortion(self):
        image = Image.new('RGB', (2928, 1200), 'black')
        draw = ImageDraw.Draw(image)
        draw.ellipse((200, 200, 600, 600), fill='red')
        draw.rectangle((0, 0, 79, 79), fill='green')
        draw.rectangle((2848, 1120, 2927, 1199), fill='blue')
        image.save(self.raw)
        record = finalize(self.raw, self.out)
        self.assertEqual(record['crop_box'], [0, 0, 2928, 1200])
        self.assertFalse(record['upscaled'])
        with Image.open(self.out) as result:
            self.assertEqual(result.size, TARGET)
            self.assertEqual(result.getpixel((5, 5))[:3], (0, 128, 0))
            self.assertEqual(result.getpixel((1458, 594))[:3], (0, 0, 255))
            circle = result.getchannel('R').point(lambda value: 255 if value > 127 else 0)
            left, top, right, bottom = circle.getbbox()
            # Raster edge coverage may differ by one pixel after filtering.
            self.assertAlmostEqual(right - left, bottom - top, delta=1)
            self.assertAlmostEqual(right - left, 200, delta=1)
            self.assertAlmostEqual(bottom - top, 200, delta=1)
        self.assertEqual(export_errors(self.root, self.out, self.requirements), [])

    def test_missing_or_impossible_keep_region_never_writes_output(self):
        for box in (None, [0,0,1,1], [0,.3,1,.2], [0,0,float('nan'),1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                finalize(self.raw, self.out, box)
            self.assertFalse(store_exists(self.out))

    def test_upscale_requires_explicit_opt_in_and_records_it(self):
        Image.new('RGB', (732,300), 'white').save(self.raw)
        with self.assertRaisesRegex(ValueError, 'allow-upscale'):
            finalize(self.raw, self.out)
        record = finalize(self.raw, self.out, allow_upscale=True)
        self.assertTrue(record['upscaled'])
        self.assertEqual(export_errors(self.root, self.out, self.requirements), [])

    def test_exact_size_still_runs_code_and_records_full_frame(self):
        Image.new('RGBA', TARGET, (20,30,40,128)).save(self.raw)
        record = finalize(self.raw, self.out)
        self.assertEqual(record['crop_box'], [0,0,1464,600])
        with Image.open(self.out) as image:
            self.assertEqual(image.getpixel((0,0)), (20,30,40,128))
        self.assertEqual(export_errors(self.root, self.out, self.requirements), [])

    def test_no_overwriting_original_or_existing_candidate(self):
        before = store_bytes(self.raw)
        with self.assertRaises(ValueError):
            finalize(self.raw, self.raw, [.1,.25,.9,.75])
        finalize(self.raw, self.out, [.1,.25,.9,.75])
        final_bytes = store_bytes(self.out)
        with self.assertRaises(ValueError):
            finalize(self.raw, self.out, [.1,.25,.9,.75])
        self.assertEqual(store_bytes(self.raw), before)
        self.assertEqual(store_bytes(self.out), final_bytes)

    def test_review_rejects_wrong_actual_size_or_missing_code_provenance(self):
        self.assertTrue(export_errors(self.root, self.raw, self.requirements))
        Image.new('RGB', TARGET, 'white').save(self.out)
        self.assertTrue(any('provenance' in e for e in export_errors(self.root, self.out, self.requirements)))

    def test_review_detects_modified_original_and_final_pixels(self):
        finalize(self.raw, self.out, [.1,.25,.9,.75])
        with Image.open(self.out) as im:
            record = im.info[METADATA_KEY]
            altered = im.convert('RGBA')
        altered.putpixel((0,0), (0,0,0,255))
        meta = PngImagePlugin.PngInfo();meta.add_text(METADATA_KEY, record)
        altered.save(self.out, pnginfo=meta)
        self.assertTrue(any('differs' in e for e in export_errors(self.root, self.out, self.requirements)))
        Image.new('RGB', (1536,1024), 'black').save(self.raw)
        self.assertTrue(any('original' in e for e in export_errors(self.root, self.out, self.requirements)))

    def test_cli_handles_paths_with_spaces(self):
        destination = self.root / 'folder with spaces/final.png'
        run = subprocess.run([sys.executable, str(SINGLE/'finalize_a_plus_image.py'), '--source', str(self.raw),
            '--output', str(destination), '--keep-box', '.1', '.25', '.9', '.75'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['output_size'], [1464,600])
        self.assertEqual(export_errors(self.root, destination, self.requirements), [])

    def test_exif_orientation_is_applied_before_keep_coordinates(self):
        image = Image.new('RGB', (1024,1536), 'white')
        exif = image.getexif();exif[274] = 6
        image.save(self.raw, exif=exif)
        record = finalize(self.raw, self.out, [.05,.25,.95,.75])
        self.assertEqual(record['source_size'], [1536,1024])
        self.assertEqual(export_errors(self.root, self.out, self.requirements), [])

    def test_png_provenance_cannot_point_outside_the_product_package(self):
        finalize(self.raw, self.out, [.1,.25,.9,.75])
        other_root = self.root / 'another-product'
        other_root.mkdir()
        self.assertTrue(export_errors(other_root, self.out, self.requirements))

    def test_standalone_a_plus_initializer_enables_required_code_export(self):
        for name, data in [('index.json', {'product_id':'p'}), ('PRODUCT_STATE.json', {'product_id':'p','sku':'p'})]:
            store_write(self.root/name, data)
        run = subprocess.run([sys.executable, str(SINGLE/'init_run_records.py'), str(self.root),
            '--run-id','standalone','--sku','p','--view','material','--a-plus'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        contract = store_read(self.root/'runs/standalone/material_generation_contract.json')
        self.assertEqual(contract['output_requirements']['postprocess'], METHOD)
        self.assertEqual([contract['output_requirements'][k] for k in ('width_px','height_px','format')], [1464,600,'PNG'])
        self.assertEqual(contract['output_requirements']['pre_crop_review'], CROP_REVIEW)

    def source_review_fixture(self, layout=None):
        contract_path = self.root/'contract.json'
        report_path = self.root/'qa/source.json'
        contract = {'candidate_id': 'fixture', 'target_view': 'detail', 'output_path': 'final.png', 'references': [], 'copy': {'title': 'FEATURE'},
                    'quality_contract': {'layout': layout or {}},
                    'output_requirements': {**self.requirements, 'pre_crop_review': CROP_REVIEW}}
        store_write(contract_path, contract)
        import hashlib
        sha = lambda path: hashlib.sha256(store_bytes(path)).hexdigest()
        image_hash = sha(self.raw)
        report = {'schema_version': 2, 'candidate_id': 'fixture', 'phase': 'SOURCE_IMAGE',
                  'candidate_sha256': image_hash, 'contract_sha256': sha(contract_path),
                  'review_binding': review_binding(self.root, contract, image_hash),
                  'inspection_method': 'VISUAL_INSPECTION', 'reviewer': 'synthetic crop fixture, not visual acceptance',
                  'composition': {'coordinate_space': 'SOURCE_IMAGE', 'image_sha256': image_hash,
                                  'annotation_method': 'ASSISTANT_VISUAL_ESTIMATE', 'boundary_certainty': 'CLEAR', 'required_content': 'COMPLETE',
                                  'product_regions': [{'label': 'red product', 'box': [.13,.34,.53,.64]}],
                                  'copy_regions': [{'label': 'feature text', 'box': [.58,.46,.75,.52]}],
                                  'protected_regions': [{'label': 'required detail', 'box': [.2,.4,.4,.5]}]},
                  'checks': {key: {'status': 'PASS', 'observation': 'synthetic crop decision'} for key in ('layout_output','design_quality')}}
        with Image.open(self.raw) as image:
            decision = assess_crop(image.size, image_hash, contract, report)
        if 'normalized_crop_box' in decision:
            report['reviewed_crop_box'] = decision['normalized_crop_box']
        report_path.parent.mkdir(parents=True)
        store_write(report_path, report)
        return contract, report, contract_path, report_path

    def test_guarded_export_derives_protected_crop_and_retains_review_provenance(self):
        contract, _, path, report = self.source_review_fixture()
        record = finalize(self.raw, self.out, package=self.root, contract_path=path, review_path=report)
        self.assertEqual(record['layout_review']['method'], CROP_REVIEW)
        self.assertEqual(export_errors(self.root, self.out, contract['output_requirements']), [])
        with Image.open(self.out) as image:
            self.assertEqual(image.size, TARGET)

    def test_guard_rejects_cut_content_uncertainty_and_unreviewed_crop_without_writing(self):
        contract, report, path, report_path = self.source_review_fixture()
        import copy
        for change in ('cut', 'uncertain', 'wrong-crop', 'failed-design'):
            data = copy.deepcopy(report)
            keep = None
            if change == 'cut': keep = [.1,.7,.9,.9]
            if change == 'uncertain': data['composition']['boundary_certainty'] = 'UNCERTAIN'
            if change == 'wrong-crop': data['reviewed_crop_box'] = [0,0,1,1]
            if change == 'failed-design': data['checks']['design_quality']['status'] = 'FAIL'
            store_write(report_path, data)
            with self.subTest(change=change), self.assertRaises(ValueError):
                finalize(self.raw, self.out, keep, package=self.root, contract_path=path, review_path=report_path)
            self.assertFalse(store_exists(self.out))

    def test_guard_rejects_projected_copy_conflict_even_if_region_fits(self):
        contract, report, path, report_path = self.source_review_fixture({'copy_box': [0,0,.6,1], 'review_constraints': {'product_clear_of_copy': True}})
        with self.assertRaisesRegex(ValueError, 'intrudes'):
            finalize(self.raw, self.out, package=self.root, contract_path=path, review_path=report_path)
        self.assertFalse(store_exists(self.out))

    def test_guard_cannot_be_bypassed_with_legacy_export_and_detects_changed_source_report(self):
        contract, report, path, report_path = self.source_review_fixture()
        legacy = self.root/'legacy.png'
        finalize(self.raw, legacy, [.1,.25,.9,.75])
        self.assertTrue(any('missing source' in e for e in export_errors(self.root, legacy, contract['output_requirements'])))
        finalize(self.raw, self.out, package=self.root, contract_path=path, review_path=report_path)
        report['checks']['layout_output']['observation'] = 'changed after export'
        store_write(report_path, report)
        self.assertTrue(any('changed' in e for e in export_errors(self.root, self.out, contract['output_requirements'])))

    def test_crop_check_only_returns_proposal_without_exporting(self):
        _, report, path, report_path = self.source_review_fixture()
        report.pop('reviewed_crop_box')
        store_write(report_path, report)
        run = subprocess.run([sys.executable, str(SINGLE/'finalize_a_plus_image.py'), '--source', str(self.raw), '--output', str(self.out),
                              '--package', str(self.root), '--contract', str(path), '--review', str(report_path), '--check-only'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'REVIEW_REQUIRED')
        self.assertIn('normalized_crop_box', json.loads(run.stdout))
        self.assertFalse(store_exists(self.out))

    def test_source_phase_draft_initializes_before_final_exists(self):
        _, _, path, _ = self.source_review_fixture()
        store_write(self.root/'PRODUCT_STATE.json', {'candidates': []})
        run = subprocess.run([sys.executable, str(SINGLE/'candidate_qa.py'), str(self.root), '--contract', str(path.name),
                              '--report', 'qa/draft-source.json', '--init', '--source-image', 'raw.png'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        draft = store_read(self.root/'qa/draft-source.json')
        self.assertEqual(draft['phase'], 'SOURCE_IMAGE')
        self.assertEqual(draft['composition']['coordinate_space'], 'SOURCE_IMAGE')
        self.assertIsNone(draft['reviewed_crop_box'])
        self.assertFalse(store_exists(self.out))


if __name__ == '__main__':
    unittest.main()
