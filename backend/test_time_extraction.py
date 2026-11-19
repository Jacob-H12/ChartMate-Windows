import unittest
from extraction import extract
class TimeExtraction(unittest.TestCase):
 def test_screenshot(self):
  text='[BLANK_AUDIO]\nIt is 8 AM, the baseline fetal heart rate is 130 beats per minute.\nBlood pressure is 180 over 66 millimeters of mercury.'
  r=extract(text)
  self.assertEqual(r['observation_time'],'08:00')
  self.assertEqual(r['fields']['fhr']['value'],'130 beats per minute')
  self.assertEqual(r['fields']['systolic']['value'],'180')
  self.assertEqual(r['fields']['diastolic']['value'],'66')
  self.assertEqual(r['unmatched'],[])
  self.assertIn('It is 8 AM',r['fields']['fhr']['source'])
 def test_clock_formats(self):
  for text,expected in [('At 8:30 PM, pulse: 80','20:30'),('It is 12 AM, pulse: 80','00:00'),('Time: 12 PM; pulse: 80','12:00'),('14:05; pulse: 80','14:05'),('It is eight a.m., the pulse is 80.','08:00')]:
   with self.subTest(text=text):self.assertEqual(extract(text)['observation_time'],expected)
 def test_invalid_ambiguous(self):
  for text in ['At 25:00, pulse: 80','At 8:75 AM, pulse: 80','It is 8, pulse: 80']:
   self.assertEqual(extract(text)['observation_time'],'')
 def test_multiple_times_no_mixing(self):
  r=extract('At 8 AM, pulse: 80. At 9 AM, FHR: 140.')
  self.assertTrue(r['time_conflict']);self.assertEqual(r['fields'],{});self.assertEqual(r['observation_time'],'')
 def test_non_observation_time(self):
  self.assertEqual(extract('Plan: review at 8 AM.')['observation_time'],'')
  self.assertEqual(extract('Ruptured membranes: at 8 AM.')['observation_time'],'')
 def test_lowercase_sentences(self):
  r=extract('it is 8 AM, the baseline fetal heart rate is 130. blood pressure is 180 over 66 millimetres of mercury.')
  self.assertEqual(r['fields']['diastolic']['value'],'66')
 def test_negation_and_no_time(self):
  self.assertNotIn('fhr',extract('At 8 AM, no fetal heart rate was obtained.')['fields'])
  self.assertEqual(extract('Pulse: 80')['observation_time'],'')
if __name__=='__main__':unittest.main()
