from __future__ import annotations
import hashlib,json,os,sqlite3,time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable,Iterator,Optional,Protocol

class DurableLogError(RuntimeError): pass
class RemoteAckError(DurableLogError): pass
class DeliveryBlocked(DurableLogError): pass

@dataclass(frozen=True)
class Event:
    conversation_id:str; event_id:str; seq:int; role:str; content:str
    created_ns:int; prev_hash:str; event_hash:str
@dataclass(frozen=True)
class CommitReceipt:
    event:Event; local_committed:bool; remote_acked:bool; remote_receipt:Optional[str]
class ReplicaSink(Protocol):
    def replicate(self,event:Event)->str: ...

class SQLiteDurableEventLog:
    def __init__(self,path,*,fail_roles=None):
        self.path=str(path); self.fail_roles=set(fail_roles or [])
        Path(self.path).parent.mkdir(parents=True,exist_ok=True); self._init()
    def _c(self):
        c=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL'); c.execute('PRAGMA foreign_keys=ON'); return c
    def _init(self):
        with closing(self._c()) as c:
            c.execute('CREATE TABLE IF NOT EXISTS events(conversation_id TEXT,event_id TEXT,seq INTEGER,role TEXT,content TEXT,created_ns INTEGER,prev_hash TEXT,event_hash TEXT,PRIMARY KEY(conversation_id,event_id),UNIQUE(conversation_id,seq))')
            c.execute('CREATE TABLE IF NOT EXISTS replica_receipts(conversation_id TEXT,event_id TEXT,event_hash TEXT,receipt TEXT,acked_ns INTEGER,PRIMARY KEY(conversation_id,event_id),FOREIGN KEY(conversation_id,event_id) REFERENCES events(conversation_id,event_id))')
            c.execute("CREATE TABLE IF NOT EXISTS replication_outbox(conversation_id TEXT,event_id TEXT,event_hash TEXT,state TEXT,attempts INTEGER DEFAULT 0,last_error TEXT,updated_ns INTEGER,PRIMARY KEY(conversation_id,event_id),FOREIGN KEY(conversation_id,event_id) REFERENCES events(conversation_id,event_id))")
    @staticmethod
    def _payload(cid,eid,seq,role,content,created,prev):
        return json.dumps({'content':content,'conversation_id':cid,'created_ns':created,'event_id':eid,'prev_hash':prev,'role':role,'seq':seq},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    def append(self,*,conversation_id,event_id,role,content,enqueue_replication=False):
        if role in self.fail_roles: raise DurableLogError(f'injected durable-write failure for role={role}')
        c=self._c()
        try:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT seq,role,content,created_ns,prev_hash,event_hash FROM events WHERE conversation_id=? AND event_id=?',(conversation_id,event_id)).fetchone()
            if row:
                seq,r,old,created,prev,h=row
                if r!=role or old!=content: raise DurableLogError('event_id replay conflict')
                if enqueue_replication: c.execute("INSERT OR IGNORE INTO replication_outbox VALUES(?,?,?,'PENDING',0,NULL,?)",(conversation_id,event_id,h,time.time_ns()))
                c.execute('COMMIT'); return Event(conversation_id,event_id,seq,role,content,created,prev,h)
            last=c.execute('SELECT seq,event_hash FROM events WHERE conversation_id=? ORDER BY seq DESC LIMIT 1',(conversation_id,)).fetchone()
            seq,prev=(1,'0'*64) if last is None else (int(last[0])+1,str(last[1])); created=time.time_ns()
            h=hashlib.sha256(self._payload(conversation_id,event_id,seq,role,content,created,prev)).hexdigest()
            c.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(conversation_id,event_id,seq,role,content,created,prev,h))
            if enqueue_replication: c.execute("INSERT INTO replication_outbox VALUES(?,?,?,'PENDING',0,NULL,?)",(conversation_id,event_id,h,time.time_ns()))
            c.execute('COMMIT'); return Event(conversation_id,event_id,seq,role,content,created,prev,h)
        except Exception:
            try:c.execute('ROLLBACK')
            except sqlite3.Error:pass
            raise
        finally:c.close()
    def mark_remote_ack(self,e,receipt):
        with closing(self._c()) as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT event_hash FROM replica_receipts WHERE conversation_id=? AND event_id=?',(e.conversation_id,e.event_id)).fetchone()
            if row and row[0]!=e.event_hash: c.execute('ROLLBACK'); raise DurableLogError('replica receipt hash conflict')
            if not row: c.execute('INSERT INTO replica_receipts VALUES(?,?,?,?,?)',(e.conversation_id,e.event_id,e.event_hash,receipt,time.time_ns()))
            c.execute("UPDATE replication_outbox SET state='ACKED',last_error=NULL,updated_ns=? WHERE conversation_id=? AND event_id=? AND event_hash=?",(time.time_ns(),e.conversation_id,e.event_id,e.event_hash)); c.execute('COMMIT')
    def record_replica_failure(self,e,error):
        with closing(self._c()) as c:
            c.execute('BEGIN IMMEDIATE'); c.execute("UPDATE replication_outbox SET state='PENDING',attempts=attempts+1,last_error=?,updated_ns=? WHERE conversation_id=? AND event_id=? AND event_hash=?",(str(error)[:2000],time.time_ns(),e.conversation_id,e.event_id,e.event_hash)); c.execute('COMMIT')
    def remote_receipt(self,e):
        with closing(self._c()) as c:r=c.execute('SELECT receipt FROM replica_receipts WHERE conversation_id=? AND event_id=? AND event_hash=?',(e.conversation_id,e.event_id,e.event_hash)).fetchone()
        return None if r is None else str(r[0])
    def outbox_state(self,cid,eid):
        with closing(self._c()) as c:r=c.execute('SELECT state FROM replication_outbox WHERE conversation_id=? AND event_id=?',(cid,eid)).fetchone()
        return None if r is None else str(r[0])
    def pending_replications(self,limit=100):
        with closing(self._c()) as c: rows=c.execute("SELECT e.conversation_id,e.event_id,e.seq,e.role,e.content,e.created_ns,e.prev_hash,e.event_hash FROM replication_outbox o JOIN events e ON e.conversation_id=o.conversation_id AND e.event_id=o.event_id WHERE o.state='PENDING' ORDER BY o.updated_ns,e.conversation_id,e.seq LIMIT ?",(limit,)).fetchall()
        return [Event(*r) for r in rows]
    def get_event(self,cid,eid):
        with closing(self._c()) as c:r=c.execute('SELECT seq,role,content,created_ns,prev_hash,event_hash FROM events WHERE conversation_id=? AND event_id=?',(cid,eid)).fetchone()
        return None if r is None else Event(cid,eid,*r)
    def events(self,cid):
        with closing(self._c()) as c:rows=c.execute('SELECT event_id,seq,role,content,created_ns,prev_hash,event_hash FROM events WHERE conversation_id=? ORDER BY seq',(cid,)).fetchall()
        return [Event(cid,*r) for r in rows]
    def verify_chain(self,cid):
        prev='0'*64
        for n,e in enumerate(self.events(cid),1):
            if e.seq!=n or e.prev_hash!=prev:return False
            if hashlib.sha256(self._payload(e.conversation_id,e.event_id,e.seq,e.role,e.content,e.created_ns,e.prev_hash)).hexdigest()!=e.event_hash:return False
            prev=e.event_hash
        return True

class JsonlFilesystemReplica:
    def __init__(self,root): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def replicate(self,e):
        d=self.root/hashlib.sha256(e.conversation_id.encode()).hexdigest()[:24]; d.mkdir(parents=True,exist_ok=True)
        f=d/f'{e.seq:012d}-{e.event_hash}.json'; data=(json.dumps(e.__dict__,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
        if f.exists():
            if f.read_bytes()!=data: raise RemoteAckError('filesystem replica collision/content mismatch')
            return f'file:{f}'
        t=d/f'.{f.name}.{os.getpid()}.tmp'
        with open(t,'xb') as h:h.write(data);h.flush();os.fsync(h.fileno())
        os.replace(t,f)
        try:
            fd=os.open(d,os.O_RDONLY);os.fsync(fd);os.close(fd)
        except OSError:pass
        return f'file:{f}'

class DurableCommitter:
    def __init__(self,log,*,replica=None,require_remote_ack=True):
        if require_remote_ack and replica is None: raise ValueError('strict remote ACK requires replica')
        self.log=log;self.replica=replica;self.require_remote_ack=require_remote_ack
    def commit(self,*,conversation_id,event_id,role,content):
        e=self.log.append(conversation_id=conversation_id,event_id=event_id,role=role,content=content,enqueue_replication=self.replica is not None)
        if self.replica is None:return CommitReceipt(e,True,False,None)
        prior=self.log.remote_receipt(e)
        if prior:return CommitReceipt(e,True,True,prior)
        try:receipt=self.replica.replicate(e)
        except Exception as x:
            self.log.record_replica_failure(e,x)
            if self.require_remote_ack:raise RemoteAckError('remote durable ACK failed') from x
            return CommitReceipt(e,True,False,None)
        self.log.mark_remote_ack(e,receipt);return CommitReceipt(e,True,True,receipt)
    def retry_pending(self,limit=100):
        out={'attempted':0,'acked':0,'failed':0}
        if self.replica is None:return out
        for e in self.log.pending_replications(limit):
            out['attempted']+=1
            try:self.log.mark_remote_ack(e,self.replica.replicate(e));out['acked']+=1
            except Exception as x:self.log.record_replica_failure(e,x);out['failed']+=1
        return out

class ModelAdapter(Protocol):
    def complete(self,user_text:str)->str:...
    def stream(self,user_text:str)->Iterable[str]:...
class OpenAIResponsesAdapter:
    def __init__(self,*,model='gpt-5.6-sol',client=None):
        self.model=model
        if client is None:
            from openai import OpenAI
            client=OpenAI()
        self.client=client
    def complete(self,t):return str(self.client.responses.create(model=self.model,input=t).output_text)
    def stream(self,t)->Iterator[str]:
        for e in self.client.responses.create(model=self.model,input=t,stream=True):
            if getattr(e,'type',None)=='response.output_text.delta' and getattr(e,'delta',None):yield str(e.delta)

class FailClosedChatHarness:
    def __init__(self,committer,model):self.committer=committer;self.model=model
    def exchange(self,*,conversation_id,request_id,user_text):
        self.committer.commit(conversation_id=conversation_id,event_id=f'{request_id}:user',role='user',content=user_text)
        aid=f'{request_id}:assistant'; old=self.committer.log.get_event(conversation_id,aid)
        if old:
            try:self.committer.commit(conversation_id=conversation_id,event_id=aid,role='assistant',content=old.content)
            except Exception as x:raise DeliveryBlocked('cached assistant durability retry failed') from x
            return old.content
        text=self.model.complete(user_text)
        try:self.committer.commit(conversation_id=conversation_id,event_id=aid,role='assistant',content=text)
        except Exception as x:raise DeliveryBlocked('assistant durability failed; delivery blocked') from x
        return text
    def stream_exchange(self,*,conversation_id,request_id,user_text):
        self.committer.commit(conversation_id=conversation_id,event_id=f'{request_id}:user',role='user',content=user_text)
        chunks=[]
        for i,delta in enumerate(self.model.stream(user_text)):
            try:self.committer.commit(conversation_id=conversation_id,event_id=f'{request_id}:assistant:chunk:{i:08d}',role='assistant_chunk',content=delta)
            except Exception as x:raise DeliveryBlocked(f'chunk {i} durability failed; render blocked') from x
            chunks.append(delta);yield delta
        try:self.committer.commit(conversation_id=conversation_id,event_id=f'{request_id}:assistant:final',role='assistant_final',content=''.join(chunks))
        except Exception as x:raise DeliveryBlocked('stream finalization durability failed') from x
