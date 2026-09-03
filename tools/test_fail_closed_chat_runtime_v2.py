import os,subprocess,sys,tempfile,types,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fail_closed_chat_runtime_v2 import *

class MemoryReplica:
    def __init__(self,fail_roles=None):self.fail_roles=set(fail_roles or []);self.events=[]
    def replicate(self,e):
        if e.role in self.fail_roles:raise RuntimeError('remote fail')
        self.events.append(e);return 'ack:'+e.event_hash
class FakeModel:
    def __init__(self,text='pong',chunks=None):self.text=text;self.chunks=chunks or ['po','ng'];self.complete_calls=0
    def complete(self,t):self.complete_calls+=1;return self.text
    def stream(self,t):yield from self.chunks
class FakeResponses:
    def __init__(self):self.calls=[]
    def create(self,**kw):
        self.calls.append(kw)
        if kw.get('stream'):return iter([types.SimpleNamespace(type='response.output_text.delta',delta='A'),types.SimpleNamespace(type='response.output_text.delta',delta='B')])
        return types.SimpleNamespace(output_text='AB')

class T(unittest.TestCase):
    def mk(self,fail_remote=None,strict=True,model=None):
        td=tempfile.TemporaryDirectory();log=SQLiteDurableEventLog(Path(td.name)/'e.db');rep=MemoryReplica(fail_remote);h=FailClosedChatHarness(DurableCommitter(log,replica=rep,require_remote_ack=strict),model or FakeModel());return td,log,rep,h
    def test_strict_happy(self):
        td,l,r,h=self.mk();self.addCleanup(td.cleanup);self.assertEqual(h.exchange(conversation_id='c',request_id='r',user_text='ping'),'pong');self.assertTrue(l.verify_chain('c'));self.assertTrue(all(l.remote_receipt(e) for e in l.events('c')))
    def test_user_remote_fail_blocks_model(self):
        m=FakeModel();td,l,r,h=self.mk({'user'},model=m);self.addCleanup(td.cleanup)
        with self.assertRaises(RemoteAckError):h.exchange(conversation_id='c',request_id='r',user_text='x')
        self.assertEqual(m.complete_calls,0);self.assertEqual(l.outbox_state('c','r:user'),'PENDING')
    def test_assistant_remote_fail_blocks_delivery_and_retry_reuses_output(self):
        m=FakeModel('stable');td,l,r,h=self.mk({'assistant'},model=m);self.addCleanup(td.cleanup)
        with self.assertRaises(DeliveryBlocked):h.exchange(conversation_id='c',request_id='r',user_text='x')
        self.assertEqual(m.complete_calls,1);r.fail_roles.clear();self.assertEqual(h.exchange(conversation_id='c',request_id='r',user_text='x'),'stable');self.assertEqual(m.complete_calls,1)
    def test_stream_write_before_render(self):
        td,l,r,h=self.mk(model=FakeModel(chunks=['A','B']));self.addCleanup(td.cleanup);g=h.stream_exchange(conversation_id='c',request_id='r',user_text='x');self.assertEqual(next(g),'A');self.assertEqual([e.role for e in l.events('c')],['user','assistant_chunk']);self.assertTrue(all(l.remote_receipt(e) for e in l.events('c')));self.assertEqual(next(g),'B');self.assertRaises(StopIteration,next,g);self.assertEqual(l.events('c')[-1].content,'AB')
    def test_stream_remote_fail_blocks_chunk(self):
        td,l,r,h=self.mk({'assistant_chunk'},model=FakeModel(chunks=['A']));self.addCleanup(td.cleanup);g=h.stream_exchange(conversation_id='c',request_id='r',user_text='x')
        with self.assertRaises(DeliveryBlocked):next(g)
        self.assertIsNone(l.remote_receipt(l.events('c')[-1]))
    def test_async_outbox_restart_retry(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);db=Path(td.name)/'e.db';l=SQLiteDurableEventLog(db);bad=MemoryReplica({'user','assistant'});h=FailClosedChatHarness(DurableCommitter(l,replica=bad,require_remote_ack=False),FakeModel());self.assertEqual(h.exchange(conversation_id='c',request_id='r',user_text='x'),'pong');self.assertEqual(len(l.pending_replications()),2);l2=SQLiteDurableEventLog(db);c=DurableCommitter(l2,replica=MemoryReplica(),require_remote_ack=False);self.assertEqual(c.retry_pending(),{'attempted':2,'acked':2,'failed':0});self.assertEqual(l2.pending_replications(),[])
    def test_filesystem_replica(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);root=Path(td.name);l=SQLiteDurableEventLog(root/'e.db');c=DurableCommitter(l,replica=JsonlFilesystemReplica(root/'r'));a=c.commit(conversation_id='c',event_id='e',role='user',content='x');b=c.commit(conversation_id='c',event_id='e',role='user',content='x');self.assertEqual(a.remote_receipt,b.remote_receipt);self.assertEqual(len(list((root/'r').rglob('*.json'))),1)
    def test_concurrency(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);l=SQLiteDurableEventLog(Path(td.name)/'e.db')
        with ThreadPoolExecutor(max_workers=8) as p:list(p.map(lambda i:l.append(conversation_id='c',event_id=f'e{i}',role='user',content=str(i)),range(24)))
        self.assertEqual([e.seq for e in l.events('c')],list(range(1,25)));self.assertTrue(l.verify_chain('c'))
    def test_process_exit_durability(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);db=Path(td.name)/'e.db';code=f"from fail_closed_chat_runtime_v2 import SQLiteDurableEventLog;l=SQLiteDurableEventLog(r'{db}');l.append(conversation_id='c',event_id='e',role='user',content='x');import os;os._exit(0)";env=dict(os.environ);env['PYTHONPATH']=str(Path(__file__).parent);subprocess.run([sys.executable,'-c',code],check=True,env=env);l=SQLiteDurableEventLog(db);self.assertEqual(l.get_event('c','e').content,'x');self.assertTrue(l.verify_chain('c'))
    def test_adapter_shape(self):
        f=types.SimpleNamespace(responses=FakeResponses());a=OpenAIResponsesAdapter(client=f);self.assertEqual(a.complete('x'),'AB');self.assertEqual(list(a.stream('x')),['A','B'])
    def test_replay_conflict_fails(self):
        td=tempfile.TemporaryDirectory();self.addCleanup(td.cleanup);l=SQLiteDurableEventLog(Path(td.name)/'e.db');l.append(conversation_id='c',event_id='e',role='user',content='x')
        with self.assertRaises(DurableLogError):l.append(conversation_id='c',event_id='e',role='user',content='y')

if __name__=='__main__':unittest.main(verbosity=2)
