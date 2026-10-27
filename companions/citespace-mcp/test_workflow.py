import json
import tempfile
import threading
import types
import unittest
from datetime import datetime
from pathlib import Path

import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        w.B=types.SimpleNamespace(TASK_ROOT=self.base,_LOCK=threading.RLock())
        self.data=self.base/'input';self.data.mkdir()
        self.record='PT J\nTI Learning analytics dashboard\nPY 2020\nUT WOS:1\nDI 10.1234/test\nDE self-regulated learning\nCR A, 2019\nAB Evidence and feedback.\nER'
        (self.data/'download.txt').write_text('FN Test\nVR 1.0\n'+self.record+'\nEF\n',encoding='utf-8')

    def tearDown(self): self.temp.cleanup()

    def prepare(self,**changes):
        args=dict(title='Test',research_question='How is feedback studied?',data_directory=str(self.data),start_year=2016,end_year=2025,node_type='Reference',k=6,rationale='Co-citation identifies shared references',sources=[])
        args.update(changes);return w.prepare(**args)

    def graph(self,body):
        p=self.base/'test.graphml'
        p.write_text('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'+body+'</graphml>',encoding='utf-8');return p

    def test_audit_and_source_preservation(self):
        before=w.digest(self.data/'download.txt');r=self.prepare()
        self.assertEqual(r['audit']['included_records'],1)
        self.assertEqual(before,w.digest(self.data/'download.txt'))
        self.assertEqual(w.evidence(r['run_id'],'feedback')['records'][0]['record_id'],'WOS:1')

    def test_identical_duplicate_removed(self):
        (self.data/'second.txt').write_text(self.record,encoding='utf-8')
        r=self.prepare();self.assertEqual(r['excluded_count'],1);self.assertEqual(r['audit']['included_records'],1)

    def test_preparation_does_not_invent_database_provenance(self):
        result=self.prepare()
        prepared=Path(result['directory'])/'data'/'download_records.txt'
        self.assertEqual(prepared.read_text(encoding='utf-8').splitlines()[0],
                         'FN ISI Export Format')
        self.assertEqual((self.data/'download.txt').read_text(encoding='utf-8').splitlines()[0], 'FN Test')
        audit=json.loads((Path(result['directory'])/'data_audit.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['input_headers'][0]['header'], 'FN Test')
        self.assertIn('not database provenance', audit['prepared_format'])

    def test_conflicting_duplicate_is_error(self):
        (self.data/'second.txt').write_text(self.record.replace('Evidence and feedback.','Different.'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Conflicting duplicate'): self.prepare()

    def test_future_year_rejected(self):
        with self.assertRaises(ValueError): self.prepare(end_year=datetime.now().year+1)

    def test_missing_reference_field(self):
        (self.data/'download.txt').write_text(self.record.replace('CR A, 2019\n',''),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Missing required'): self.prepare()

    def test_incomplete_record_rejected(self):
        (self.data/'download.txt').write_text(self.record[:-2],encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Unterminated'): self.prepare()

    def test_scoped_duplicate_graph_keys(self):
        p=self.graph('<key id="year" for="node" attr.name="year" attr.type="string"/><key id="year" for="edge" attr.name="year" attr.type="integer"/><graph edgedefault="undirected"><node id="a"><data key="year">2020</data></node><node id="b"/><edge source="a" target="b"><data key="year">2021</data></edge></graph>')
        g=w.parse_graph(p);self.assertEqual(g['nodes'][0]['attributes']['year'],'2020');self.assertEqual(g['edges'][0]['attributes']['year'],2021)

    def test_dangling_edge_rejected(self):
        p=self.graph('<graph><node id="a"/><edge source="a" target="missing"/></graph>')
        with self.assertRaisesRegex(ValueError,'Dangling'): w.parse_graph(p)

    def test_duplicate_node_rejected(self):
        p=self.graph('<graph><node id="a"/><node id="a"/></graph>')
        with self.assertRaisesRegex(ValueError,'duplicate node'): w.parse_graph(p)

    def test_xml_entity_rejected(self):
        p=self.base/'bad.graphml';p.write_text('<!DOCTYPE x [<!ENTITY x "bad">]><graphml/>')
        with self.assertRaisesRegex(ValueError,'DTD'): w.parse_graph(p)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError): w.run_path('../anything')

    def test_submitted_run_cannot_restart(self):
        r=self.prepare();p,m=w.read_manifest(r['run_id']);w.checkpoint(p,m,'test',state='submitted')
        with self.assertRaisesRegex(ValueError,'never blindly replayed'): w.start(r['run_id'])

    def test_graph_missing_metrics_and_report_evidence(self):
        r=self.prepare();p,m=w.read_manifest(r['run_id'])
        g=self.graph('<key id="centrality" for="node" attr.name="centrality" attr.type="double"/><graph edgedefault="undirected"><node id="a"/><node id="b"/><edge source="a" target="b"/></graph>')
        target=p/'project'/'2.graphml';target.write_bytes(g.read_bytes())
        w.checkpoint(p,m,'fixture',state='graph_ready',graph={'path':target.name,'sha256':w.digest(target)})
        result=w.analyze(r['run_id']);self.assertEqual(result['metrics']['density_derived'],1)
        self.assertEqual(result['metrics']['centrality_values_present'],0);self.assertIsNone(result['metrics']['Q'])
        self.assertEqual(w.neighborhood(r['run_id'],'a')['neighbors'][0]['id'],'b')
        with self.assertRaisesRegex(ValueError,'Unknown evidence'):
            w.render_report(r['run_id'],[{'heading':'Wrong','text':'x','evidence_ids':['node:unknown']}])
        report=w.render_report(r['run_id'],[{'heading':'Observed','text':'Two nodes connected by one edge.','evidence_ids':['graph:summary']}])
        self.assertTrue(Path(report['report_html']).is_file())
        self.assertIn('CiteSpace GraphML',Path(report['graph_svg']).read_text())

    def test_added_source_ids_stable(self):
        r=self.prepare();s={'title':'Paper','url':'https://doi.org/10.1234/a','note':'Metadata only'}
        a=w.add_sources(r['run_id'],[s]);b=w.add_sources(r['run_id'],[s])
        self.assertEqual(a['evidence_ids'],b['evidence_ids']);self.assertEqual(len(b['sources']),1)


if __name__=='__main__': unittest.main(verbosity=2)
