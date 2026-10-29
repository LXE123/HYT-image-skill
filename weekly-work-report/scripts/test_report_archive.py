import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

spec=importlib.util.spec_from_file_location('archive',Path(__file__).with_name('report_archive.py'))
archive=importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

class ArchiveBehavior(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config={'version':1,'timezone':'Asia/Shanghai','first_meeting':'2026-10-15'}

    def period(self,day):
        return archive.paths(self.root,self.config,archive.iso(day))

    def test_wednesday_thursday_boundary(self):
        for day in ['2026-10-08','2026-10-14']:
            p=self.period(day)
            self.assertEqual((p['week_number'],p['period_start'],p['period_end'],p['meeting_date']),(1,'2026-10-08','2026-10-14','2026-10-15'))
        for day in ['2026-10-15','2026-10-16']:
            p=self.period(day)
            self.assertEqual((p['week_number'],p['period_start'],p['meeting_date']),(2,'2026-10-15','2026-10-22'))
        meeting=archive.paths(self.root,self.config,archive.iso('2026-10-15'),meeting=True)
        self.assertEqual((meeting['week_number'],meeting['period_end']),(1,'2026-10-14'))

    def test_new_year_does_not_reset(self):
        before=self.period('2026-12-30')
        after=self.period('2026-12-31')
        self.assertEqual(after['week_number'],before['week_number']+1)
        self.assertEqual(after['meeting_date'],'2027-01-07')
        self.assertEqual(self.period('2027-01-01')['week_number'],after['week_number'])

    def test_earlier_archive_does_not_become_week_zero(self):
        with self.assertRaises(ValueError): self.period('2026-10-07')

    def test_prepare_only_creates_date_directories(self):
        p=self.period('2026-10-15');archive.prepare(p)
        daily=Path(p['week_dir'])/'daily-reports'
        self.assertEqual(len(list(daily.iterdir())),7)
        self.assertEqual(list(daily.rglob('*.md')),[])

    def test_duplicate_is_idempotent_and_conflict_is_preserved(self):
        target=self.root/'上午.md'
        archive.write_bundle({target:b'plan'})
        self.assertFalse(archive.write_bundle({target:b'plan'})[0]['changed'])
        with self.assertRaises(ValueError): archive.write_bundle({target:b'changed'})
        self.assertEqual(target.read_bytes(),b'plan')

    def test_update_requires_current_hash(self):
        target=self.root/'下午.md';target.write_bytes(b'old')
        with self.assertRaises(ValueError): archive.write_bundle({target:b'new'},True,{target:'stale'})
        self.assertEqual(target.read_bytes(),b'old')
        archive.write_bundle({target:b'new'},True,{target:archive.sha(target)})
        self.assertEqual(target.read_bytes(),b'new')

    def test_pair_conflict_prevents_partial_update(self):
        md,html=self.root/'report.md',self.root/'report.html'
        md.write_bytes(b'old-md');html.write_bytes(b'old-html')
        with self.assertRaises(ValueError):
            archive.write_bundle({md:b'new-md',html:b'new-html'},True,{md:archive.sha(md),html:'stale'})
        self.assertEqual(md.read_bytes(),b'old-md')
        self.assertEqual(html.read_bytes(),b'old-html')

    def test_collection_reports_unrecorded_slots_and_no_other_week(self):
        p=self.period('2026-10-16');archive.prepare(p)
        Path(p['morning']).write_text('计划',encoding='utf-8')
        result=archive.collect(self.root,self.config,archive.iso('2026-10-22'))
        self.assertEqual(len(result['files']),1)
        self.assertEqual(len(result['unrecorded_slots']),13)
        self.assertEqual(result['files'][0]['date'],'2026-10-16')

    def test_html_data_cannot_close_script(self):
        data=archive.validate({'headline':'</script><script>bad()</script>',
            'work':[{'title':'任务','summary':'进行中','items':[{'tag':'计划','text':'尚未完成'}]}],
            'goals':[], 'next':[{'title':'测试','text':'继续验证'}],
            'summary':[{'title':'状态','text':'待验证'}]})
        rendered=archive.html(data,self.period('2026-10-15'))
        self.assertNotIn('<script>bad()',rendered)
        self.assertIn('\\u003c/script\\u003e',rendered)
        self.assertIn('尚未完成',archive.markdown(data,self.period('2026-10-15')))

    def test_live_lock_does_not_get_removed_by_competitor(self):
        with archive.locked(self.root):
            with self.assertRaises(ValueError):
                with archive.locked(self.root): pass
            self.assertTrue((self.root/'.report-write.lock').exists())
        self.assertFalse((self.root/'.report-write.lock').exists())

    def historical(self):
        return {'version':2,'timezone':'Asia/Shanghai','anchor_meeting':'2026-10-15','anchor_week_number':4,
                'historical_reports':[{'week_number':2,'meeting_date':'2026-09-25','period_start':'2026-09-21','period_end':'2026-09-25'},
                                      {'week_number':3,'meeting_date':'2026-10-09','period_start':'2026-10-06','period_end':'2026-10-09'}]}

    def test_fourth_week_anchor_and_next_week(self):
        c=self.historical()
        for day,number in [('2026-10-08',4),('2026-10-09',4),('2026-10-14',4),('2026-10-15',5),('2026-10-16',5),('2026-10-29',7)]:
            self.assertEqual(archive.paths(self.root,c,archive.iso(day))['week_number'],number)

    def test_first_week_has_no_previous_goal_section(self):
        data=archive.validate({'headline':'入职首周完成流程原型',
            'work':[{'title':'流程原型','summary':'第一阶段建设','items':[{'tag':'验证','text':'完成原型验证'}]}],
            'goals':[], 'next':[{'title':'业务试用','text':'条件具备后开展'}],
            'summary':[{'title':'成果','text':'完成流程梳理'}]})
        rendered=archive.markdown(data,self.period('2026-10-15'))
        self.assertNotIn('上期目标',rendered)
        self.assertIn('## 二、下阶段重点',rendered)
        self.assertIn('## 三、总结',rendered)

    def test_historical_friday_meeting_and_overlap(self):
        c=self.historical()
        historical=archive.paths(self.root,c,archive.iso('2026-10-09'),meeting=True)
        daily=archive.paths(self.root,c,archive.iso('2026-10-09'))
        self.assertEqual(historical['week_number'],3)
        self.assertEqual(historical['period_start'],'2026-10-06')
        self.assertEqual(daily['week_number'],4)

    def test_holiday_gap_not_silently_assigned(self):
        with self.assertRaises(ValueError):archive.paths(self.root,self.historical(),archive.iso('2026-10-01'))

    def test_historical_prepare_preserves_actual_coverage(self):
        p=archive.paths(self.root,self.historical(),archive.iso('2026-09-25'),meeting=True)
        archive.prepare(p)
        self.assertEqual(len(list((Path(p['week_dir'])/'daily-reports').iterdir())),5)

    def test_previous_report_uses_archive_not_seven_day_subtraction(self):
        p=archive.paths(self.root,self.historical(),archive.iso('2026-10-09'),meeting=True)
        archive.prepare(p);Path(p['report_md']).write_text('历史报告',encoding='utf-8')
        actual=archive.collect(self.root,self.historical(),archive.iso('2026-10-15'))
        self.assertEqual(actual['previous_report'],p['report_md'])

    def test_collection_excludes_meeting_day_and_finds_legacy_thursday_next_period(self):
        c=self.historical()
        for day in ['2026-10-22','2026-10-28','2026-10-29']:
            # Simulate previously archived Friday–Thursday directories without moving them.
            week='week5' if day=='2026-10-22' else 'week6'
            folder=self.root/week/'daily-reports'/day
            folder.mkdir(parents=True,exist_ok=True)
            for session in ['上午','下午']:
                (folder/(session+'.md')).write_text(day+session,encoding='utf-8')
        current=archive.collect(self.root,c,archive.iso('2026-10-29'))
        self.assertEqual({x['date'] for x in current['files']},{'2026-10-22','2026-10-28'})
        following=archive.collect(self.root,c,archive.iso('2026-11-05'))
        self.assertEqual({x['date'] for x in following['files']},{'2026-10-29'})
        p=archive.paths(self.root,c,archive.iso('2026-10-29'))
        self.assertEqual(p['week_name'],'week7')
        self.assertIn('week6',p['morning'])
        self.assertEqual(Path(p['morning']).read_text(),'2026-10-29上午')

    def test_duplicate_daily_copies_are_deduplicated_or_fail_on_conflict(self):
        for week in ['week1','week2']:
            folder=self.root/week/'daily-reports/2026-10-15'
            folder.mkdir(parents=True)
            (folder/'上午.md').write_text('same')
        result=archive.collect(self.root,self.config,archive.iso('2026-10-22'))
        self.assertEqual(len(result['files']),1)
        (self.root/'week1/daily-reports/2026-10-15/上午.md').write_text('different')
        with self.assertRaisesRegex(ValueError,'不同内容'):
            archive.collect(self.root,self.config,archive.iso('2026-10-22'))

    def test_cli_init_and_meeting_paths_do_not_advance_the_anchor_week(self):
        script=str(Path(archive.__file__))
        def run(*args):
            result=subprocess.run([sys.executable,'-B',script,'--root',str(self.root),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        initial=run('init','--anchor-meeting','2026-10-15','--anchor-week-number','4')
        self.assertEqual(initial['week_number'],4)
        daily=run('paths','--date','2026-10-29')
        meeting=run('paths','--date','2026-10-29','--meeting')
        self.assertEqual(daily['week_number'],7)
        self.assertEqual(meeting['week_number'],6)
        self.assertEqual(meeting['period_end'],'2026-10-28')

if __name__=='__main__':unittest.main()
