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
from finalize_a_plus_image import TARGET, METHOD, METADATA_KEY, crop_geometry, finalize, export_errors


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
        original = self.raw.read_bytes()
        record = finalize(self.raw, self.out, [.1, .25, .95, .75])
        self.assertEqual(self.raw.read_bytes(), original)
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

    def test_missing_or_impossible_keep_region_never_writes_output(self):
        for box in (None, [0,0,1,1], [0,.3,1,.2], [0,0,float('nan'),1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                finalize(self.raw, self.out, box)
            self.assertFalse(self.out.exists())

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
        before = self.raw.read_bytes()
        with self.assertRaises(ValueError):
            finalize(self.raw, self.raw, [.1,.25,.9,.75])
        finalize(self.raw, self.out, [.1,.25,.9,.75])
        final_bytes = self.out.read_bytes()
        with self.assertRaises(ValueError):
            finalize(self.raw, self.out, [.1,.25,.9,.75])
        self.assertEqual(self.raw.read_bytes(), before)
        self.assertEqual(self.out.read_bytes(), final_bytes)

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
            (self.root/name).write_text(json.dumps(data))
        run = subprocess.run([sys.executable, str(SINGLE/'init_run_records.py'), str(self.root),
            '--run-id','standalone','--sku','p','--view','material','--a-plus'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        contract = json.loads((self.root/'runs/standalone/material_generation_contract.json').read_text())
        self.assertEqual(contract['output_requirements']['postprocess'], METHOD)
        self.assertEqual([contract['output_requirements'][k] for k in ('width_px','height_px','format')], [1464,600,'PNG'])


if __name__ == '__main__':
    unittest.main()
