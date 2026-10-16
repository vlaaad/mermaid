import unittest
from PIL import Image
from tools.structure_check import audit

class StructureCheckTests(unittest.TestCase):
    def test_blue_water_cannot_satisfy_geometry_presence(self):
        with self.assertRaises(ValueError):audit(Image.new('RGB',(100,100),(20,130,190)))
    def test_empty_and_misplaced_geometry_fail(self):
        target={'pillar':{'box':[.4,.1,.2,.8],'min_row_coverage':.7}}
        image=Image.new('RGB',(100,100),'black')
        self.assertFalse(audit(image,target)['all_required_present'])
        image.paste('white',(10,10,20,90))
        self.assertFalse(audit(image,target)['all_required_present'])
    def test_actual_vertical_geometry_passes_but_small_cap_does_not(self):
        target={'pillar':{'box':[.4,.1,.2,.8],'min_row_coverage':.7}}
        image=Image.new('RGB',(100,100),'black')
        image.paste('white',(45,10,55,90))
        self.assertTrue(audit(image,target)['all_required_present'])
        image=Image.new('RGB',(100,100),'black');image.paste('white',(40,10,60,15))
        self.assertFalse(audit(image,target)['all_required_present'])
