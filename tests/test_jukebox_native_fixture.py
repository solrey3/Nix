"""End-to-end native evidence readers on a synthetic filesystem and fake IO."""
import copy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import jukebox_playback as p
import jukebox_native as n
import jukebox_window as w
import jukebox_cli as cli
from test_jukebox_playback import Fixture
from schedule_fixtures import SCHEDULE_SQL, cold_state, status as schedule_status


class NativeFixture:
    def __init__(self):
        self.f=Fixture();f=self.f
        self.paths={'home':f.home,'root':f.root/'master','project':f.root/'project',
          'app':f.root/'project/App','data':f.root/'project/App/data',
          'telemetry':f.root/'project/Telemetry/JukeboxApp','system':f.root/'selected-system','hm':f.root/'selected-home',
          'proc':f.root/'proc','store':f.store,'cgroup':f.root/'cgroup','uid':os.getuid()}
        for key in ('data','telemetry','proc','cgroup') :self.paths[key].mkdir(parents=True,mode=0o700)
        for name in ('Music','Playlists','Staging'):
            (self.paths['root']/name).mkdir(parents=True)
            (self.paths['project']/name).symlink_to(self.paths['root']/name)
        (self.paths['root']/'Playlists/Fixture.m3u').write_text('#EXTM3U\n')
        for key in ('system','hm'):
            target=f.store/(key+'-profile');target.mkdir();self.paths[key].symlink_to(target)
        self.fragment=f.home/'.config/systemd/user/jukebox-manager.service';self.fragment.parent.mkdir(parents=True)
        self.fragment.write_text('[Service]\nExecStart=fixture\n')
        self.scan={'running':False,'phase':'complete'}
        (self.paths['data']/'scan-state.json').write_text(json.dumps(self.scan));(self.paths['data']/'scan-state.json').chmod(0o600)
        (self.paths['app']/'.env').write_text('API_TOKEN=SYNTHETIC_SEALED_ONLY\n');(self.paths['app']/'.env').chmod(0o600)
        db=sqlite3.connect(self.paths['data']/'jukebox.sqlite');db.executescript('CREATE TABLE tracks(id INTEGER PRIMARY KEY,title TEXT);INSERT INTO tracks VALUES(1,"fixture");' + SCHEDULE_SQL + ';');db.close()
        ep=self.paths['app']/'node_modules/esbuild/package.json';ep.parent.mkdir(parents=True);ep.write_text('{"version":"0.25"}')
        binary=self.paths['app']/'node_modules/@esbuild/linux-x64/bin/esbuild';binary.parent.mkdir(parents=True);binary.write_text('fixture, never executed')
        self.pid=100;self.active=True;self.loaded=False;self.calls=[];self.roots={};self.stop_policy='no'
        self.captured_at=1000000;self.cold_schedule=cold_state(self.captured_at);self.on_start=None
        self.node=f.store/'node-fixture';self.node.write_text('fixture, never executed')
        self.create_proc()
        owner=self
        class Runner:
            tools={'systemctl':'/fixture/systemctl','git':'/fixture/git','nix-store':'/fixture/nix-store'}
            def drain(self):pass
            def run(self,name,args,**kwargs):return owner.run(name,args,**kwargs)
        class API:
            def get(self,endpoint):return owner.api(endpoint)
        self.io=n.NativeIO(self.paths,Runner(),API(),now=lambda:1000,sleep=lambda _:None)
        # Native clock reader is virtual-proc aware; monotonic remains real.
        boot=self.paths['proc']/'sys/kernel/random/boot_id';boot.parent.mkdir(parents=True);boot.write_text('fixture-boot\n')

    def create_proc(self):
        proc=self.paths['proc']/str(self.pid);task=proc/'task'/str(self.pid);task.mkdir(parents=True)
        (task/'comm').write_text('MainThread\n');(task/'children').write_text('')
        worker=proc/'task'/str(self.pid+1000);worker.mkdir();(worker/'comm').write_text('WorkerThread\n')
        fields=['S']+['0']*18+['12345']+['0']*4
        (proc/'stat').write_text(str(self.pid)+' (node) '+' '.join(fields))
        (proc/'cmdline').write_bytes(b'node\0--import\0tsx\0server/index.ts\0')
        (proc/'exe').symlink_to(self.node)
        (proc/'cwd').symlink_to(self.paths['app'])
        (proc/'fd').mkdir();(proc/'fd/7').symlink_to(self.paths['data']/'jukebox.sqlite')
        group=self.paths['cgroup']/'user.slice'/n.UNIT;group.mkdir(parents=True,exist_ok=True);(group/'cgroup.procs').write_text(str(self.pid))

    def unit(self,name):
        v={key:'' for key in n.PROPS}
        v.update(MainPID=str(self.pid) if self.active else '0',InvocationID='fixture-'+str(self.pid),ActiveState='active' if self.active else 'inactive',
                 SubState='running' if self.active else 'dead',FragmentPath=str(self.fragment),KillMode='control-group',
                 SendSIGKILL=self.stop_policy,TimeoutStopUSec='30s',Result='success',ControlGroup='/user.slice/'+n.UNIT,
                 WorkingDirectory=str(self.paths['app']))
        if name!=n.UNIT:v.update(MainPID='200' if name=='mpd.service' else '300',InvocationID=name,FragmentPath='/fixture/'+name,ActiveState='active',SubState='running')
        elif self.loaded:v['DropInPaths']=str(self.f.home/p.TARGETS['90-playback.conf'])
        return v

    def run(self,name,args,**kwargs):
        self.calls.append((name,list(args)))
        if name=='git':return '' if 'status' in args else 'a'*40+'\n'+'b'*40
        if name=='nix-store':
            if '--add-root' in args:
                root=Path(args[args.index('--add-root')+1]);manifest=args[-1];root.symlink_to(manifest);self.roots[manifest]=str(root)
            if '--references' in args:return str(self.f.a.directory)
            if '--roots' in args:return self.roots.get(args[-1],'')+' -> '+args[-1]
            return ''
        if 'show' in args:
            unit=next(x for x in args if x.endswith('.service'));return '\n'.join(k+'='+v for k,v in self.unit(unit).items())
        self.assert_action(args)
        if 'stop' in args:
            shutil.rmtree(self.paths['proc']/str(self.pid));self.active=False
            (self.paths['cgroup']/'user.slice'/n.UNIT/'cgroup.procs').write_text('')
        elif 'start' in args:
            self.pid+=1;self.active=True;self.create_proc();self.captured_at+=100
            self.cold_schedule=cold_state(self.captured_at)
            if self.on_start:self.on_start()
        elif 'daemon-reload' in args:self.loaded=(self.f.home/p.TARGETS['90-playback.conf']).is_symlink()
        return ''

    def assert_action(self,args):
        p.require(tuple(['systemctl',*args]) in p.COMMANDS.values(),'Unexpected fixture action')

    def api(self,endpoint):
        p.require(endpoint in w.ENDPOINTS,'Unexpected fixture endpoint')
        if endpoint=='scan':return copy.deepcopy(self.scan)
        if endpoint=='operations/schedule':
            self.captured_at+=1
            db=sqlite3.connect(self.paths['data']/'jukebox.sqlite')
            try:row=db.execute('SELECT json FROM collector_schedule_v1').fetchone()
            finally:db.close()
            state=json.loads(row[0]) if row else copy.deepcopy(self.cold_schedule)
            state.pop('root',None)
            return schedule_status(state,self.captured_at)
        if endpoint=='discovery':return []
        if endpoint=='discovery/runs':return {'rows':[]}
        zones={}
        if self.loaded:zones={'bravo':{'host':'127.0.0.1','port':6600,'musicPrefix':'Music/'}}
        return {'root':'/mnt/files2/Jukebox','mpdPathMapping':True,'writes':False,'libraryEdits':True,'indexedCount':1,
                'scan':copy.deepcopy(self.scan),'zones':zones,'navidrome':None}

    def seal_backup(self):
        self.io.observe();data=copy.deepcopy(self.io.offline)
        target=self.paths['data']/'deployment-backups'/('publisher-reviewed-'+'a'*32);target.mkdir(parents=True,mode=0o700)
        source=sqlite3.connect((self.paths['data']/'jukebox.sqlite').as_uri()+'?mode=ro',uri=True)
        dest=sqlite3.connect(target/'jukebox.sqlite');source.backup(dest);dest.close();source.close();(target/'jukebox.sqlite').chmod(0o600)
        shutil.copyfile(self.paths['app']/'.env',target/'configuration.env');(target/'configuration.env').chmod(0o600)
        (target/'app-files').mkdir(mode=0o700)
        for name in data['state']:
            shutil.copyfile(self.paths['data']/name,target/'app-files'/name);(target/'app-files'/name).chmod(0o600)
        (target/'telemetry-metadata').mkdir(mode=0o700)
        for name in data['telemetry']:
            copied=target/'telemetry-metadata'/name;copied.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copyfile(self.paths['telemetry']/name,copied);copied.chmod(0o600)
        receipt={'schema':1,'dataset':data};(target/'receipt.json').write_bytes(p.canonical(receipt));(target/'receipt.json').chmod(0o600)
        return target

    def make_adapter(self,artifact):
        prototype=object.__new__(w.WindowAdapter);prototype.io=self.io
        observed=prototype._observe();context=prototype._context(observed)
        boot,mono,utc=self.io.clock()
        plan={'schema':1,'id':'a'*32,'publisher':'b'*64,'artifact':artifact.record() if artifact else None,'window':w.WINDOW,
          'failurePolicy':w.POLICY,'allowPreparation':True,'allowManagerStopStart':True,'allowUserDaemonReload':True,
          'bootId':boot,'createdMonotonic':mono,'createdUtc':utc,'expiresMonotonic':mono+600,'expiresUtc':utc+600,
          'backup':{'id':'a'*32,'hash':p.digest((self.paths['data']/'deployment-backups'/('publisher-reviewed-'+'a'*32)/'receipt.json').read_bytes())}
                    if (self.paths['data']/'deployment-backups'/('publisher-reviewed-'+'a'*32)/'receipt.json').exists()
                    else {'id':'a'*32,'hash':'f'*64},
          'expected':{k:context[k] for k in w.FIELDS}}
        return w.WindowAdapter(self.io,plan,p.digest(p.canonical(plan)),'b'*64,artifact)

    def close(self):self.f.close()


class NativeFixtureTests(unittest.TestCase):
    def test_all_native_readers_backup_stop_closure_and_ready_with_fake_commands(self):
        x=NativeFixture()
        try:
            (x.paths['telemetry']/'transactions').mkdir(mode=0o700)
            (x.paths['telemetry']/'transactions/fixture.json').write_text('{"status":"complete"}')
            x.seal_backup();a=x.make_adapter(x.f.a);x.f.publisher.adapter=a
            r=x.f.publisher.review(x.f.a,approve=True);x.f.publisher.apply(r['id'],approve=True)
            self.assertEqual(x.f.publisher.inspect()['state'],'owned')
            self.assertTrue(x.loaded)
            # Rollback restores absence with native evidence, no backup reuse by guess.
            x.f.publisher.adapter=x.make_adapter(None)
            r=x.f.publisher.review(None,approve=True,rollback=True);x.f.publisher.apply(r['id'],approve=True,rollback=True)
            self.assertEqual(x.f.publisher.inspect()['state'],'empty')
            actions=[args for name,args in x.calls if name=='systemctl' and 'show' not in args]
            self.assertEqual(actions,[['--user','stop',n.UNIT],['--user','daemon-reload'],['--user','start',n.UNIT]]*2)
        finally:x.close()

    def test_gated_cli_plan_and_fd_flow_uses_only_fixture_dependencies(self):
        x=NativeFixture()
        try:
            x.seal_backup();base=x.make_adapter(x.f.a);plan=copy.deepcopy(base.plan);plan['publisher']=cli.code_identity()
            path=x.f.home/'approved-plan.json';path.write_bytes(p.canonical(plan));path.chmod(0o600)
            args=SimpleNamespace(mode='review',approve=True,activation_plan=str(path),expected_plan_sha256=p.digest(p.canonical(plan)),
                manifest=None,expected_manifest_sha256=None,expected_source_revision=None,review_id=None,api_token_fd=None)
            def invoke():
                read,write=os.pipe();os.write(write,b'SYNTHETIC_TOKEN_0123456789012345\n');os.close(write);args.api_token_fd=read
                try:
                    with patch.object(cli,'fixed_paths',return_value=x.paths),patch.object(cli,'Artifact',side_effect=x.f.load), \
                         patch.object(cli,'OwnedRunner',return_value=x.io.runner),patch.object(cli,'LocalAPI',return_value=x.io.api), \
                         patch.object(cli,'NativeIO',return_value=x.io):
                        return cli.run(args)
                finally:os.close(read)
            reviewed=invoke();self.assertNotIn('phase',reviewed)
            self.assertFalse(any(name=='systemctl' and 'show' not in argv for name,argv in x.calls))
            args.mode='apply';args.review_id=reviewed['id'];result=invoke();self.assertEqual(result['phase'],'verified')
            # No activation plan can be reused as a consumed core review.
            with self.assertRaises(p.Refusal):invoke()
            bad=copy.deepcopy(plan);bad['allowUserDaemonReload']=False;path.write_bytes(p.canonical(bad));args.expected_plan_sha256=p.digest(p.canonical(bad))
            with patch.object(cli,'fixed_paths',side_effect=AssertionError('must not inspect host')):
                with self.assertRaises(p.Refusal):cli.run(args)
        finally:x.close()

    def test_private_credential_fd_bounds_and_no_argv_channel(self):
        for token in (b'x'*24,b'x'*256+b'\n',b'x'*24+b'\n\n',b'x'*258,b'x'*24+b'\r'):
            read,write=os.pipe();os.write(write,token);os.close(write)
            try:
                if token in (b'x'*24,b'x'*256+b'\n'):self.assertEqual(cli.token_from_fd(read),token.removesuffix(b'\n'))
                else:
                    with self.assertRaises(p.Refusal):cli.token_from_fd(read)
            finally:os.close(read)
        with self.assertRaises(p.Refusal):cli.token_from_fd(0)

    def test_sealed_backup_missing_copy_modified_database_and_private_mode_rejected(self):
        for kind in ('missing','database','mode','environment','receipt'):
            x=NativeFixture()
            try:
                target=x.seal_backup();a=x.make_adapter(x.f.a);context=a.snapshot()
                if kind=='missing':(target/'app-files/scan-state.json').unlink()
                elif kind=='database':
                    db=sqlite3.connect(target/'jukebox.sqlite');db.execute('DELETE FROM tracks');db.commit();db.close()
                elif kind=='mode':(target/'jukebox.sqlite').chmod(0o644)
                elif kind=='environment':(target/'configuration.env').write_text('modified')
                else:(target/'receipt.json').write_text('{"schema":1,"dataset":{}}')
                with self.assertRaises((p.Refusal,OSError)):a.backup(context)
                self.assertFalse(any(name=='systemctl' and 'show' not in args for name,args in x.calls))
            finally:x.close()

    def test_deployment_export_proof_and_uncertain_export_are_checked(self):
        x=NativeFixture()
        try:
            target=x.seal_backup();a=x.make_adapter(x.f.a);context=a.snapshot()
            reference=a.plan['backup']
            proof={'schema':1,'receipt':reference,'datasetHash':p.digest(p.canonical(x.io.offline))}
            (target/'export.json').write_bytes(p.canonical(proof));(target/'export.json').chmod(0o600)
            self.assertEqual(a.backup(context),reference)
            for name in ('.receipt-export-intent.json','.receipt-pending'):
                path=target/name;path.write_bytes(b'uncertain');path.chmod(0o600)
                with self.assertRaises(p.Refusal):a.backup(context)
                path.unlink() # fixture only, never a recovery procedure
            proof['datasetHash']='0'*64;(target/'export.json').write_bytes(p.canonical(proof))
            with self.assertRaises(p.Refusal):a.backup(context)
        finally:x.close()

    def test_fixed_and_observed_storage_separate_project_from_physical_media(self):
        account=SimpleNamespace(pw_uid=1234,pw_dir='/home/budchris')
        with patch.object(n.pwd,'getpwnam',return_value=account),patch.object(n.os,'geteuid',return_value=1234), \
             patch.object(n.socket,'gethostname',return_value='bravo'):
            paths=n.fixed_paths()
        self.assertEqual(paths['root'],Path('/mnt/files2/Jukebox'))
        self.assertEqual(paths['project'],Path('/home/budchris/Projects/Jukebox'))
        self.assertEqual(paths['app'],paths['project']/'App')
        self.assertEqual(paths['data'],paths['app']/'data')
        self.assertEqual(paths['telemetry'],paths['project']/'Telemetry/JukeboxApp')
        x=NativeFixture()
        try:
            x.io.observe()
            git=[args for tool,args in x.calls if tool=='git']
            self.assertTrue(git)
            self.assertTrue(all(args[args.index('-C')+1]==str(x.paths['project']) for args in git))
            old=x.unit
            x.unit=lambda name:{**old(name),'WorkingDirectory':str(x.paths['root']/'App')}
            with self.assertRaises(p.Refusal):x.io.observe()
            x.unit=old
            cwd=x.paths['proc']/str(x.pid)/'cwd';cwd.unlink();cwd.symlink_to(x.paths['root']/'Music')
            with self.assertRaises(p.Refusal):x.io.observe()
        finally:x.close()

    def test_sealed_namespace_is_checked_before_any_sqlite_open(self):
        for relative in ('foreign.json', 'app-files/foreign.json', 'telemetry-metadata/foreign.json',
                         'jukebox.sqlite-wal', 'jukebox.sqlite-shm', 'jukebox.sqlite-journal'):
            with self.subTest(relative=relative):
                x=NativeFixture()
                try:
                    target=x.seal_backup();a=x.make_adapter(x.f.a);context=a.snapshot()
                    foreign=target/relative;foreign.write_bytes(b'');foreign.chmod(0o600)
                    with patch.object(w.sqlite3,'connect',side_effect=AssertionError('SQLite must not open')):
                        with self.assertRaises(p.Refusal):a.backup(context)
                    self.assertTrue(foreign.exists(), 'No cleanup of rejected evidence')
                    self.assertFalse(any(name=='systemctl' and 'show' not in args for name,args in x.calls))
                finally:x.close()

    def test_actual_owned_pid_or_cgroup_not_closed_blocks_after_stop(self):
        x=NativeFixture()
        try:
            a=x.make_adapter(x.f.a);context=a.snapshot()
            x.active=False # claim unit stopped, but retain owned process and group
            with self.assertRaises(p.Refusal):a.stopped(context)
            shutil.rmtree(x.paths['proc']/str(x.pid))
            with self.assertRaises(p.Refusal):a.stopped(context)
        finally:x.close()

    def test_wrong_database_fd_worker_or_foreign_dropin_are_not_proven(self):
        for kind in ('database','worker','dropin'):
            x=NativeFixture()
            try:
                if kind=='database':
                    path=x.paths['proc']/str(x.pid)/'fd/7';path.unlink();path.symlink_to(x.f.root/'other-db')
                elif kind=='worker':
                    task=x.paths['proc']/str(x.pid)/'task/9999';task.mkdir();(task/'comm').write_text('WorkerThread')
                else:
                    old=x.unit;x.unit=lambda name:{**old(name),'DropInPaths':'/foreign/unit.conf'} if name==n.UNIT else old(name)
                with self.assertRaises(p.Refusal):x.io.observe()
            finally:x.close()


if __name__=='__main__':unittest.main()
