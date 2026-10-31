"""Window policy and native reader/runner tests: fixtures only, no real services/API."""
import copy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jukebox_playback as p
import jukebox_window as w
import jukebox_native as n
from test_jukebox_playback import Fixture
from schedule_fixtures import cold_state, status as schedule_status


class WindowIO:
    def __init__(self, fixture):
        self.f = fixture
        self.now = ['boot', 100, 1000]
        self.active = True
        self.calls = []
        self.receipts = []
        self.bad = None
        self.immutable = {k: p.digest(k.encode()) for k in ('profiles','tools','unit','stopPolicy','source','privateState')}
        self.invocation = p.digest(b'first')
        self.capture = 1000000
        self.schedule_state = cold_state(self.capture)

    def clock(self): return tuple(self.now)
    def observe(self, stopped=False):
        scan = {'running': False, 'phase': 'complete'}
        zones = {}
        target = self.f.home / p.TARGETS['playback.env']
        if target.exists():
            import shlex
            zones = json.loads(shlex.split(target.read_text().splitlines()[0])[0].split('=',1)[1])
        config = {'root':'/mnt/files2/Jukebox','mpdPathMapping':True,'writes':False,'libraryEdits':True,
                  'zones':zones,'navidrome':None,'scan':scan}
        result = {**self.immutable,'invocation':self.invocation,'processClosed':not self.active,
                  'jobsIdle':True,'config':config,'scan':scan,
                  'schedule':schedule_status(copy.deepcopy(self.schedule_state),self.capture),
                  'scheduleStorage':{'kind':'empty'},'zonesOwned':True}
        self.capture += 1
        if self.bad == 'busy': result['jobsIdle'] = False
        if self.bad == 'worker': result['processClosed'] = False
        if self.bad == 'schedule': result['schedule']['capability'] = True
        if self.bad == 'flags': result['config']['writes'] = True
        return result
    def register_root(self,a,path): self.calls.append('root'); path.symlink_to(a.path)
    def verify_root(self,a,path):
        p.require(path.is_symlink() and os.readlink(path)==str(a.path),'Root unknown')
    def backup(self,before):
        r={'id':format(len(self.receipts),'032x'),'hash':p.digest(p.canonical(before))}
        self.receipts.append(r);return r
    def verify_backup(self,r,before): p.require(r in self.receipts and r['hash']==p.digest(p.canonical(before)),'Backup not proven')
    def command(self,argv):
        p.require(argv in p.COMMANDS.values(),'Unsupported action');self.calls.append(argv)
        if argv==p.COMMANDS['stop']: self.active=False
        if argv==p.COMMANDS['start']:
            self.active=True;self.invocation=p.digest(self.invocation.encode())
            self.schedule_state=cold_state(self.capture)
    def wait_config(self): self.calls.append('read-only-config')
    def drain(self): pass


def adapter(f,io,artifact):
    prototype=object.__new__(w.WindowAdapter);prototype.io=io
    observed=prototype._observe();context=prototype._context(observed)
    plan={'schema':1,'id':'a'*32,'publisher':'b'*64,'artifact':artifact.record() if artifact else None,
          'window':w.WINDOW,'failurePolicy':w.POLICY,'allowPreparation':True,'allowManagerStopStart':True,
          'allowUserDaemonReload':True,'bootId':'boot','createdMonotonic':100,'createdUtc':1000,
          'expiresMonotonic':700,'expiresUtc':1600,
          'backup':{'id':format(len(io.receipts),'032x'),'hash':p.digest(p.canonical(observed))},
          'expected':{k:context[k] for k in w.FIELDS}}
    return w.WindowAdapter(io,plan,p.digest(p.canonical(plan)),'b'*64,artifact)


class WindowTests(unittest.TestCase):
    def test_window_adapter_install_noop_and_initial_rollback_integration(self):
        f=Fixture()
        try:
            io=WindowIO(f);a=adapter(f,io,f.a);f.publisher.adapter=a
            r=f.publisher.review(f.a,approve=True);f.publisher.apply(r['id'],approve=True)
            self.assertEqual([c for c in io.calls if isinstance(c,tuple)],[p.COMMANDS[k] for k in ('stop','reload','start')])
            a=adapter(f,io,f.a);f.publisher.adapter=a
            r=f.publisher.review(f.a,approve=True);f.publisher.apply(r['id'],approve=True)
            self.assertEqual(len([c for c in io.calls if isinstance(c,tuple)]),3)
            a=adapter(f,io,None);f.publisher.adapter=a
            r=f.publisher.review(None,approve=True,rollback=True);f.publisher.apply(r['id'],approve=True,rollback=True)
            self.assertEqual(f.publisher.inspect()['state'],'empty')
        finally:f.close()

    def test_explicit_plan_permissions_pins_policy_and_bounded_window(self):
        f=Fixture()
        try:
            io=WindowIO(f);a=adapter(f,io,f.a)
            for key,value in (('window','lease'),('failurePolicy','retry'),('allowUserDaemonReload',False),
                              ('allowManagerStopStart',False),('expiresUtc',2000),('schema',True)):
                with self.subTest(key=key):
                    plan=copy.deepcopy(a.plan);plan[key]=value
                    with self.assertRaises(p.Refusal):w.WindowAdapter(io,plan,p.digest(p.canonical(plan)),'b'*64,f.a)
            with self.assertRaises(p.Refusal):w.WindowAdapter(io,a.plan,'0'*64,'b'*64,f.a)
            for key,value in ((0,'newboot'),(1,99),(1,700),(2,999),(2,1600)):
                io.now=['boot',100,1000];io.now[key]=value
                with self.assertRaises(p.Refusal):a.snapshot()
            self.assertEqual(io.calls,[])
        finally:f.close()

    def test_observation_not_lease_unknown_or_stale_evidence_never_eligible(self):
        f=Fixture()
        try:
            io=WindowIO(f);a=adapter(f,io,f.a)
            for bad in ('busy','schedule','flags'):
                io.bad=bad
                with self.assertRaises(p.Refusal):a.snapshot()
            io.bad=None;io.immutable['profiles']=p.digest(b'changed')
            with self.assertRaises(p.Refusal):a.snapshot()
            self.assertEqual(io.calls,[])
        finally:f.close()

    def test_review_cannot_switch_plan_or_artifact_after_independent_binding(self):
        f=Fixture()
        try:
            io=WindowIO(f);a=adapter(f,io,f.a);f.publisher.adapter=a
            reviewed=f.publisher.review(f.a,approve=True)
            changed=copy.deepcopy(a.plan);changed['id']='d'*32
            f.publisher.adapter=w.WindowAdapter(io,changed,p.digest(p.canonical(changed)),'b'*64,f.a)
            with self.assertRaises(p.Refusal):f.publisher.apply(reviewed['id'],approve=True)
            self.assertFalse(any(isinstance(x,tuple) for x in io.calls))
            other=f.artifact(revision='e'*40,pretty=True)
            with self.assertRaises(p.Refusal):a.admit_target(other)
        finally:f.close()

    def test_stopped_and_post_start_profile_flags_and_resource_drift(self):
        for bad in ('worker','profiles','privateState','flags'):
            f=Fixture()
            try:
                io=WindowIO(f);a=adapter(f,io,f.a);context=a.snapshot()
                io.active=False
                if bad=='worker':io.bad=bad
                elif bad in io.immutable:io.immutable[bad]=p.digest(b'changed')
                else:io.bad=bad
                if bad=='flags':
                    io.active=True
                    with self.assertRaises(p.Refusal):a.ready(f.a,context)
                else:
                    with self.assertRaises(p.Refusal):a.stopped(context)
            finally:f.close()


class NativeTests(unittest.TestCase):
    def test_owned_runner_timeout_overflow_drain_no_kill_or_retry(self):
        for args,limit in ((['-c','import time;time.sleep(.15)'],100),
                           (['-c','import time;print("x"*5000,flush=True);time.sleep(.15)'],10)):
            runner=object.__new__(n.OwnedRunner);runner.home='/tmp';runner.uid=os.getuid();runner.tools={'git':sys.executable};runner.pending=[]
            start=time.monotonic()
            with self.assertRaises(p.Refusal):runner.run('git',args,timeout=.02,limit=limit)
            self.assertEqual(len(runner.pending),1)
            with self.assertRaises(p.Refusal):runner.run('git',['--version'])
            runner.drain();self.assertGreater(time.monotonic()-start,.10);self.assertEqual(runner.pending,[])

    def test_database_and_private_file_integrity_no_migration(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);db=root/'jukebox.sqlite'
            con=sqlite3.connect(db);con.executescript('CREATE TABLE tracks(id INTEGER PRIMARY KEY,title TEXT);INSERT INTO tracks VALUES(1,"fixture");');con.close()
            before=n.database_digest(db);self.assertEqual(before['tables']['tracks']['count'],1)
            self.assertEqual(n.database_digest(db),before)
            os.link(db,root/'foreign');
            with self.assertRaises(p.Refusal):n.database_digest(db)
            (root/'foreign').unlink()
            f=root/'private';f.write_bytes(b'SYNTHETIC_SECRET');f.chmod(0o600)
            self.assertEqual(n.safe_file(f,uid=os.getuid(),private=True),b'SYNTHETIC_SECRET')
            f.chmod(0o644)
            with self.assertRaises(p.Refusal):n.safe_file(f,uid=os.getuid(),private=True)
            f.unlink();f.symlink_to(db)
            with self.assertRaises((p.Refusal,OSError)):n.safe_file(f)

    def test_inventory_excludes_db_without_read_and_unknown_dirs_block(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            with open(root/'jukebox.sqlite','wb') as out:out.truncate(40*1024*1024)
            self.assertEqual(n.file_inventory(root,exclude=('jukebox.sqlite',)),{})
            (root/'unexpected-logs').mkdir()
            with self.assertRaises(p.Refusal):n.file_inventory(root,exclude=('jukebox.sqlite',))

    def test_readonly_api_endpoint_allowlist_redirect_and_error_redaction(self):
        api=n.LocalAPI(b'SYNTHETIC_TOKEN_0123456789012345')
        class Opener:
            def open(self,*args,**kwargs):raise RuntimeError('SYNTHETIC_SECRET')
        api.opener=Opener()
        for endpoint in ('playback','scan/start','config'):
            with self.assertRaises(p.Refusal) as error:api.get(endpoint)
            self.assertNotIn('SYNTHETIC_SECRET',str(error.exception))
        with self.assertRaises(p.Refusal):n.NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_api_bounded_body_transport_and_fixed_credential_destination(self):
        from types import SimpleNamespace
        class Response:
            status=200
            def __init__(self,body):
                self.body=body;self.closed=False;self.timeouts=[]
                self.fp=SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
            def read1(self,count):
                out,self.body=self.body[:count],self.body[count:];return out
            def __enter__(self):return self
            def __exit__(self,*_):self.closed=True
        class Opener:
            def __init__(self,response):self.response=response;self.requests=[]
            def open(self,request,**kwargs):self.requests.append(request);return self.response
        api=n.LocalAPI(b'SYNTHETIC_TOKEN_0123456789012345')
        response=Response(b'{"ok":true}');api.opener=Opener(response)
        self.assertEqual(api.get('config'),{'ok':True});self.assertTrue(response.closed)
        self.assertEqual(api.opener.requests[0].full_url,'http://127.0.0.1:3080/api/config')
        self.assertTrue(all(0<t<=10 for t in response.timeouts))
        for body in (b'x'*2_000_001,b'{"a":1,"a":2}'):
            response=Response(body);api.opener=Opener(response)
            with self.assertRaises(p.Refusal):api.get('config')
            self.assertTrue(response.closed)
        response=Response(b'{}');response.status=302;api.opener=Opener(response)
        with self.assertRaises(p.Refusal):api.get('config')
        self.assertTrue(response.closed)

    def test_root_commands_are_scoped_no_build_and_registration_not_assumed(self):
        f=Fixture()
        try:
            root=f.home/p.STATE/'roots';root.mkdir(parents=True)
            class Runner:
                def __init__(self):self.calls=[];self.proven=False
                def run(self,name,args,**kwargs):
                    self.calls.append((name,args))
                    if '--references' in args:return str(f.a.directory)
                    if '--roots' in args:return str(root/f.a.hash)+' -> '+str(f.a.path) if self.proven else ''
                    return ''
                def drain(self):pass
            r=Runner();io=n.NativeIO({'home':f.home},r,None)
            io.register_root(f.a,root/f.a.hash)
            self.assertEqual(len(r.calls),3)
            for _,args in r.calls:
                self.assertIn('substitute',args);self.assertIn('false',args);self.assertIn('max-jobs',args);self.assertIn('0',args)
            (root/f.a.hash).symlink_to(f.a.path)
            with self.assertRaises(p.Refusal):io.verify_root(f.a,root/f.a.hash)
            r.proven=True;io.verify_root(f.a,root/f.a.hash)
            with self.assertRaises(p.Refusal):io.register_root(f.a,f.home/'foreign')
        finally:f.close()

    def test_unit_escalation_policy_refuses_before_api_or_dataset(self):
        with tempfile.TemporaryDirectory() as home:
            home=Path(home);fragment=home/'.config/systemd/user/jukebox-manager.service';fragment.parent.mkdir(parents=True);fragment.write_text('fixture')
            class Runner:
                def run(self,*args,**kwargs):
                    data={k:'' for k in n.PROPS};data.update(FragmentPath=str(fragment),SendSIGKILL='yes',KillMode='control-group')
                    return '\n'.join(k+'='+v for k,v in data.items())
            io=n.NativeIO({'home':home,'uid':os.getuid()},Runner(),None)
            with self.assertRaises(p.Refusal):io.observe()


if __name__=='__main__':unittest.main()
