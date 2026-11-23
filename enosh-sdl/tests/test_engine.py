import json
import unittest
from enosh_sdl import decide
from enosh_sdl.examples import EXAMPLES
from enosh_sdl.fusion import normalize, fuse
from enosh_sdl.scheduler import wrap, phase_windows, schedule
from enosh_sdl.benchmark import benchmark

class SemanticEngineTests(unittest.TestCase):
    def test_normalize_arabic(self):
        self.assertIn('اضاءة',normalize('الإِضاءة'))
    def test_quote_intent(self):
        x=decide({'domain':'automation','text':'محتاج عرض سعر لغرفة صوت'})
        self.assertEqual(x['intent'],'request_quote')
        self.assertEqual(x['proposed_action'],'draft_quote_questions')
    def test_audio_transcript(self):
        x=decide({'domain':'automation','audio':{'transcript':'عاوز احجز معاينة للموقع','confidence':.93}})
        self.assertEqual(x['intent'],'request_booking')
    def test_vision_robot(self):
        x=decide({'domain':'robot','text':'هات الكوباية','vision':['cup']})
        self.assertEqual(x['proposed_action'],'propose_fetch_plan')
    def test_no_camera_clarify(self):
        self.assertEqual(decide({'domain':'robot','text':'هات الكوباية'})['route'],'clarify')
    def test_liquid_clarify(self):
        x=decide({'domain':'robot','text':'هات الكوباية لو مفيهاش مياه','vision':['cup','water']})
        self.assertEqual(x['route'],'clarify')
    def test_presenter_no_interrupt(self):
        x=decide({'domain':'presenter','text':'معلومة جديدة','context':{'guest_speaking':True,'turn_available':False}})
        self.assertEqual(x['route'],'wait')
    def test_presenter_free_turn(self):
        x=decide({'domain':'presenter','text':'معلومة جديدة','context':{'turn_available':True}})
        self.assertIn(x['route'],('rule','light','deep'))
    def test_emergency_sensors_hard_priority(self):
        for policy in ('sdl','always_deep','event_only'):
            x=decide({'domain':'robot','sensors':{'emergency_stop':True}},policy=policy)
            self.assertEqual(x['route'],'safe_stop')
            self.assertEqual(x['execution_status'],'safe_stop_proposed')
    def test_obstacle_stop(self):
        x=decide({'domain':'robot','text':'امشي قدام','sensors':{'obstacle_distance_m':0.12}})
        self.assertEqual(x['route'],'safe_stop')
    def test_money_needs_approval(self):
        self.assertTrue(decide({'domain':'automation','text':'حول فلوس للبنك'})['requires_approval'])
    def test_delete_requires_approval(self):
        self.assertTrue(decide({'domain':'automation','text':'احذف كل ملفات العملاء'})['requires_approval'])
    def test_external_send_requires_approval(self):
        self.assertTrue(decide({'domain':'automation','text':'محتاج سعر','context':{'external_send':True}})['requires_approval'])
    def test_confidence_under_threshold(self):
        self.assertEqual(decide({'text':'اشرحلي حالة النظام','confidence':.2})['route'],'clarify')
    def test_all_examples_are_json_serializable(self):
        for ex in EXAMPLES:
            out=decide(ex['observation'])
            json.dumps(out,ensure_ascii=False)
            self.assertEqual(out['real_tool_calls'] if 'real_tool_calls' in out else 0,0)
    def test_ollama_hint_cannot_override_hazard(self):
        x=decide({'domain':'robot','text':'اشرحلي','sensors':{'emergency_stop':True},
                  'semantic_hint':{'intent':'greeting','confidence':1}})
        self.assertEqual(x['route'],'safe_stop')
    def test_model_hint_cannot_override_delete(self):
        x=decide({'text':'احذف كل ملفات العملاء',
                  'semantic_hint':{'intent':'greeting','confidence':1}})
        self.assertEqual(x['route'],'review')
    def test_zero_input_ignore(self):
        self.assertEqual(decide({})['route'],'ignore')
    def test_invalid_weight(self):
        with self.assertRaises(ValueError):decide({'text':'hello'},energy_weight=-1)

class SchedulingTests(unittest.TestCase):
    def test_phase_windows(self):
        w=phase_windows(3,dt=.008,k=8)
        self.assertTrue(all(w[i+1]>w[i] for i in range(len(w)-1)))
    def test_direct_no_wait(self):
        s=schedule([.03,.17,.45],'direct')
        self.assertEqual(s['mean_wait_ms'],0.)
        self.assertEqual(s['n_wakeups'],3)
    def test_fixed_batching(self):
        s=schedule([.07,.08,.14,.46],'fixed')
        self.assertEqual(s['n_wakeups'],2)
        self.assertLessEqual(s['max_wait_ms'],550)
    def test_phase_bounded_wait(self):
        s=schedule([.03,.07,.09,.51,2.21,3.56],'phase',duration_s=5,k=0)
        self.assertLessEqual(s['max_wait_ms'],550.01)
    def test_benchmark_variants(self):
        x=benchmark(n=100,seed=24)
        self.assertEqual(len(x['variants']),6)
        self.assertTrue(all(i['real_tool_calls']==0 for i in x['variants']))
        self.assertEqual(x['variants'][2]['inference_count'],x['variants'][3]['inference_count'])
        self.assertEqual(x['variants'][2]['inference_count'],x['variants'][4]['inference_count'])
        self.assertEqual(x['variants'][2]['approval_blocks'],x['variants'][3]['approval_blocks'])
    def test_phase_fallback_at_zero_coupling(self):
        x=benchmark(n=100,k=0)
        self.assertGreaterEqual(x['variants'][3]['mean_dispatch_wait_ms'],0)

class V03Tests(unittest.TestCase):
    """Regression tests for the v0.3 review fixes."""
    def test_send_wording_requires_approval_without_flag(self):
        for t in ('ابعت ايميل للعميل بكل الأسعار','please email the contract to the client','انشر البوست'):
            self.assertTrue(decide({'domain':'automation','text':t})['requires_approval'],t)
    def test_delete_paraphrase_requires_approval(self):
        self.assertTrue(decide({'text':'امسح كل الملفات بتاعة العملاء'})['requires_approval'])
    def test_no_substring_false_hazard(self):
        self.assertNotEqual(decide({'text':'ده أخطر سؤال في المشروع'})['route'],'safe_stop')
    def test_latin_cue_is_whole_token(self):
        f=fuse({'text':'which file is this'})
        self.assertFalse(f['cues']['greeting'])
    def test_arabic_clitics_still_match(self):
        self.assertEqual(fuse({'text':'هات الكوباية'})['intent'],'fetch_cup')
        self.assertTrue(fuse({'text':'شغل النور'})['cues']['light'])
    def test_quality_proxy_reported_for_inference_routes(self):
        x=decide({'text':'اشرح ازاي نطور الدقة؟'},policy='always_deep')
        self.assertEqual(x['route'],'deep'); self.assertIsNotNone(x['quality_proxy'])
        self.assertIsNone(decide({})['quality_proxy'])
    def test_v02_reference_numbers_unchanged(self):
        v={i['name'][0]:i for i in benchmark(n=200,seed=24)['variants']}
        self.assertEqual([v[L]['energy_j_assumed'] for L in 'ABCDE'],[144.495,87.305,54.055,47.155,48.305])
    def test_matched_control_grid(self):
        from enosh_sdl.scheduler import matched_grid
        p,o=matched_grid(31,k=8)
        self.assertAlmostEqual(p,0.408,places=3); self.assertTrue(0<=o<p)
    def test_gate_stats_consistent(self):
        from enosh_sdl.scheduler import phase_window_stats
        s=phase_window_stats(31,k=8)
        self.assertEqual(s['crossings'],s['windows']+s['rejected'])
    def test_fixed_offset_shifts_grid(self):
        s=schedule([0.05],'fixed',fixed_period=0.4,fixed_offset=0.1)
        self.assertAlmostEqual(s['mean_wait_ms'],50.0,places=2)
    def test_probe_set_runs(self):
        from enosh_sdl.probes import evaluate
        r=evaluate(decide)
        self.assertEqual(r['n'],len(r['rows']))
        none_row=r['confusion']['none']
        self.assertEqual(none_row['safe_stop']+none_row['review'],0)

if __name__=='__main__':unittest.main()
