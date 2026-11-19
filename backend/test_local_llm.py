import io,json,unittest
from unittest.mock import patch
import local_llm as llm
TEXT='>> It is 8 AM. The baseline fetal heart rate is 130 beats per minute. Blood pressure is 180 over 66 millimeters of mercury.'
def evidence(v=None,s=''):return {'value':v,'source':s}
def response():return {'observations':[{'date':evidence(),'time':evidence('08:00','It is 8 AM.'),'stage':evidence(),'values':[{'key':'fhr','value':'130 bpm','source':'The baseline fetal heart rate is 130 beats per minute.','uncertain':False},{'key':'systolic','value':'180','source':'Blood pressure is 180 over 66 millimeters of mercury.','uncertain':False},{'key':'diastolic','value':'66','source':'Blood pressure is 180 over 66 millimeters of mercury.','uncertain':False}],'warnings':[]}],'unassigned':[]}
class Tests(unittest.TestCase):
 def test_whitespace_variations_preserve_original_quotes(self):
  for separator in ('\n','\r\n','\t','   ','\u00a0',' \n\t '):
   with self.subTest(separator=repr(separator)):
    text=TEXT.replace(' ',separator)
    d=llm.validate(response(),text)['observations'][0]
    self.assertEqual(d['observation_time'],'08:00')
    self.assertEqual(d['fields']['fhr']['value'],'130 bpm')
    self.assertEqual(d['fields']['systolic']['value'],'180')
    self.assertEqual(d['fields']['fhr']['source'],response()['observations'][0]['values'][0]['source'].replace(' ',separator))
    self.assertIn(d['time_sources'][0],text)
 def test_quote_whitespace_is_also_normalized(self):
  d=response();d['observations'][0]['values'][0]['source']=' \n'+d['observations'][0]['values'][0]['source'].replace(' ','\n')+'\t'
  result=llm.validate(d,TEXT)['observations'][0]['fields']['fhr']
  self.assertEqual(result['value'],'130 bpm');self.assertIn(result['source'],TEXT)
 def test_content_changes_are_not_whitespace(self):
  for changed in ('is 140','is not 130','is 13 0'):
   with self.subTest(changed=changed):
    text=TEXT.replace('is 130',changed).replace(' ','\n')
    self.assertEqual(llm.validate(response(),text)['observations'][0]['fields']['fhr']['value'],'')
  self.assertEqual(llm.original_source('Blood-pressure','Blood pressure'),'')
  self.assertEqual(llm.original_source(' \n\t ',TEXT),'')
 def test_normalized_request_and_original_validation(self):
  text=TEXT.replace(' ','\r\n\t')
  with patch.object(llm,'build_opener') as m:
   m.return_value.open.return_value=io.BytesIO(json.dumps({'message':{'content':json.dumps(response())}}).encode())
   result=llm.extract_local(text)
   body=json.loads(m.return_value.open.call_args.args[0].data)
   self.assertEqual(body['messages'][1]['content'],TEXT)
   self.assertEqual(result['observations'][0]['fields']['fhr']['value'],'130 bpm')
   self.assertIn(result['observations'][0]['fields']['fhr']['source'],text)
 def test_valid(self):
  d=llm.validate(response(),TEXT)['observations'][0];self.assertEqual(d['observation_time'],'08:00');self.assertEqual(d['fields']['systolic']['value'],'180');self.assertNotIn('temperature',d['fields'])
 def test_evidence(self):
  d=response();d['observations'][0]['values'][0]['source']='Invented quote'
  self.assertEqual(llm.validate(d,TEXT)['observations'][0]['fields']['fhr']['value'],'')
 def test_uncertain(self):
  d=response();d['observations'][0]['values'][0]['uncertain']=True
  self.assertEqual(llm.validate(d,TEXT)['observations'][0]['fields']['fhr']['value'],'')
 def test_duplicate(self):
  d=response();d['observations'][0]['values'].append(d['observations'][0]['values'][0].copy())
  self.assertTrue(llm.validate(d,TEXT)['observations'][0]['fields']['fhr']['conflict'])
 def test_bad_time(self):
  d=response();d['observations'][0]['time']['value']='25:00'
  self.assertEqual(llm.validate(d,TEXT)['observations'][0]['observation_time'],'')
 def test_unknown_field(self):
  d=response();d['observations'][0]['values'][0]['key']='invented'
  with self.assertRaises(ValueError):llm.validate(d,TEXT)
 def test_multiple(self):
  d=response();d['observations'].append(response()['observations'][0]);self.assertEqual(len(llm.validate(d,TEXT)['observations']),2)
 def test_request_mock(self):
  with patch.object(llm,'build_opener') as m:
   m.return_value.open.return_value=io.BytesIO(json.dumps({'message':{'content':json.dumps(response())},'done_reason':'stop'}).encode())
   self.assertEqual(llm.extract_local(TEXT)['observations'][0]['observation_time'],'08:00')
   req=m.return_value.open.call_args.args[0];body=json.loads(req.data)
   self.assertEqual(req.full_url,'http://127.0.0.1:11434/api/chat');self.assertEqual(body['format'],llm.SCHEMA);self.assertFalse(body['think']);self.assertEqual(body['keep_alive'],0)
 def test_truncated(self):
  with patch.object(llm,'build_opener') as m:
   m.return_value.open.return_value=io.BytesIO(b'{"done_reason":"length"}')
   with self.assertRaises(ValueError):llm.extract_local(TEXT)
 def test_no_silent_truncate(self):
  with self.assertRaises(ValueError):llm.extract_local('a'*12001)
if __name__=='__main__':unittest.main()
