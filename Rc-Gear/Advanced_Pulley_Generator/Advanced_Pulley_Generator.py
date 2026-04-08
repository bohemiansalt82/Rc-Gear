import adsk.core
import adsk.fusion
import traceback
import math
import os
import json

# Advanced Timing Pulley Generator Add-in
# v1.1.10: 입력값 저장(Persistence) 기능 추가
VERSION = "1.1.10"

app = adsk.core.Application.get()
ui = app.userInterface
handlers = []

COMMAND_ID = 'Advanced_Pulley_Generator'
COMMAND_NAME = 'Advanced Pulley Generator'
COMMAND_DESCRIPTION = f'[{VERSION}] 마지막 입력값 기억 기능'

# 설정 파일 경로
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'settings.json')

def mm_to_cm(val): return val / 10.0

def load_settings():
    """저장된 설정을 불러옵니다. 파일이 없으면 기본값을 반환합니다."""
    defaults = {
        'pitch': 0.3, 'tooth_h': 0.114, 'total_h': 0.21,
        'teeth': 17, 'clearance': 0.02, 'fillet_r': 0.019,
        'width': 0.4, 'flange_h': 0.1, 'flange_t': 0.1,
        'bore': 0.898, 'save_settings': True
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
                defaults.update(saved)
        except: pass
    return defaults

def save_settings(params):
    """현재 파라미터를 JSON 파일로 저장합니다."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(params, f)
    except: pass

def get_largest_profile(sketch):
    if sketch.profiles.count == 0: return None
    best_p = None
    max_a = -1
    for i in range(sketch.profiles.count):
        p = sketch.profiles.item(i)
        try:
            a = p.areaProperties().area
            if a > max_a:
                max_a = a
                best_p = p
        except: pass
    return best_p

def create_advanced_pulley(params):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent
        extrudes = root_comp.features.extrudeFeatures
        sketches = root_comp.sketches
        xy_plane = root_comp.xYConstructionPlane
        
        z = params['teeth']
        width_cm = mm_to_cm(params['width'])
        f_t_cm = mm_to_cm(params['flange_t'])
        
        pd_cm = mm_to_cm((z * params['pitch']) / math.pi)
        od_cm = pd_cm - mm_to_cm(params['pld'] * 2)
        r_outer = od_cm / 2
        r_inner = r_outer - mm_to_cm(params['tooth_h'] + 0.1)

        # 치형 생성 (v1.1.7+ 안정화 버전)
        sk = sketches.add(xy_plane)
        ap = (2 * math.pi) / z
        hb = (mm_to_cm(params['clearance'] + params['pitch']*0.5)/2)/r_outer
        ht = (mm_to_cm(params['clearance'] + params['pitch']*0.35)/2)/r_inner
        
        p1_pts, p2_pts, p3_pts, p4_pts = [], [], [], []
        for i in range(z):
            tc = i * ap
            p1_a, p2_a, p3_a, p4_a = tc-hb, tc-ht, tc+ht, tc+hb
            p1_pts.append(sk.sketchPoints.add(adsk.core.Point3D.create(r_outer*math.cos(p1_a), r_outer*math.sin(p1_a), 0)))
            p2_pts.append(sk.sketchPoints.add(adsk.core.Point3D.create(r_inner*math.cos(p2_a), r_inner*math.sin(p2_a), 0)))
            p3_pts.append(sk.sketchPoints.add(adsk.core.Point3D.create(r_inner*math.cos(p3_a), r_inner*math.sin(p3_a), 0)))
            p4_pts.append(sk.sketchPoints.add(adsk.core.Point3D.create(r_outer*math.cos(p4_a), r_outer*math.sin(p4_a), 0)))

        for i in range(z):
            sk.sketchCurves.sketchLines.addByTwoPoints(p1_pts[i], p2_pts[i])
            sk.sketchCurves.sketchLines.addByTwoPoints(p2_pts[i], p3_pts[i])
            sk.sketchCurves.sketchLines.addByTwoPoints(p3_pts[i], p4_pts[i])
            sk.sketchCurves.sketchArcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p4_pts[i], p1_pts[(i+1)%z])

        prof = get_largest_profile(sk)
        if not prof: return

        ex_in = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ex_in.setDistanceExtent(False, adsk.core.ValueInput.createByReal(width_cm))
        main_ext = extrudes.add(ex_in)
        p_body = main_ext.bodies.item(0)

        # 플랜지
        f_dia = od_cm + mm_to_cm(params['flange_h'] * 2)
        for z_off, dist in [(0, -f_t_cm), (width_cm, f_t_cm)]:
            if z_off == 0:
                curr_plane = xy_plane
            else:
                plane_input = root_comp.constructionPlanes.createInput()
                plane_input.setByOffset(xy_plane, adsk.core.ValueInput.createByReal(z_off))
                curr_plane = root_comp.constructionPlanes.add(plane_input)
            sk_f = sketches.add(curr_plane)
            sk_f.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0,0,0), f_dia/2)
            pf = get_largest_profile(sk_f)
            if pf:
                ex_f = extrudes.createInput(pf, adsk.fusion.FeatureOperations.JoinFeatureOperation)
                ex_f.setDistanceExtent(False, adsk.core.ValueInput.createByReal(dist))
                extrudes.add(ex_f)

        # 보어 (v1.1.9 관통 로직)
        sk_b = sketches.add(xy_plane)
        sk_b.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0,0,0), mm_to_cm(params['bore'])/2)
        pb = get_largest_profile(sk_b)
        if pb:
            cut_in = extrudes.createInput(pb, adsk.fusion.FeatureOperations.CutFeatureOperation)
            cut_in.setDistanceExtent(True, adsk.core.ValueInput.createByReal(10.0))
            extrudes.add(cut_in)

        # 필렛
        f_r_val = mm_to_cm(params['fillet_r'])
        if f_r_val > 0:
            try:
                fillets = root_comp.features.filletFeatures
                edge_col = adsk.core.ObjectCollection.create()
                for e in p_body.edges:
                    g1, g2 = e.startVertex.geometry, e.endVertex.geometry
                    if abs(g1.x - g2.x) < 0.001 and abs(g1.y - g2.y) < 0.001:
                        if abs(e.length - width_cm) < 0.01:
                            edge_col.add(e)
                if edge_col.count > 0:
                    f_in = fillets.createInput()
                    f_in.addConstantRadiusEdgeSet(edge_col, adsk.core.ValueInput.createByReal(f_r_val), True)
                    fillets.add(f_in)
            except: pass

        ui.messageBox(f"[{VERSION}] 생성 완료! 현재 설정이 저장되었습니다.")
    except:
        ui.messageBox(f"[{VERSION}] 오류:\n" + traceback.format_exc())

class AdvancedPulleyExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            # args.command.commandInputs를 사용하는 것이 더 안정적입니다.
            eventArgs = adsk.core.CommandEventArgs.cast(args)
            inputs = eventArgs.command.commandInputs
            
            # 입력 항목이 존재하는지 확인하며 안전하게 가져옵니다.
            save_chk_input = inputs.itemById('save_settings')
            save_chk = save_chk_input.value if save_chk_input else True
            
            # 다른 입력 항목들도 안전하게 참조
            pitch_input = inputs.itemById('pitch')
            tooth_h_input = inputs.itemById('tooth_h')
            total_h_input = inputs.itemById('total_h')
            teeth_input = inputs.itemById('teeth')
            clearance_input = inputs.itemById('clearance')
            fillet_r_input = inputs.itemById('fillet_r')
            width_input = inputs.itemById('width')
            flange_h_input = inputs.itemById('flange_h')
            flange_t_input = inputs.itemById('flange_t')
            bore_input = inputs.itemById('bore')

            if not all([pitch_input, tooth_h_input, total_h_input, teeth_input]):
                ui.messageBox('필수 입력 항목을 찾을 수 없습니다.')
                return

            p = pitch_input.value * 10
            th = tooth_h_input.value * 10
            tot = total_h_input.value * 10
            
            raw_params = {
                'pitch': p, 'tooth_h': th, 'total_h': tot,
                'teeth': teeth_input.valueOne,
                'clearance': clearance_input.value * 10 if clearance_input else 0.2,
                'fillet_r': fillet_r_input.value * 10 if fillet_r_input else 0.19,
                'width': width_input.value * 10 if width_input else 4.0,
                'flange_h': flange_h_input.value * 10 if flange_h_input else 1.0,
                'flange_t': flange_t_input.value * 10 if flange_t_input else 1.0,
                'bore': bore_input.value * 10 if bore_input else 9.0,
                'save_settings': save_chk
            }
            
            if save_chk:
                # 보정된 cm 값으로 저장 (ValueInput 호환용)
                save_data = raw_params.copy()
                for k in ['pitch','tooth_h','total_h','clearance','fillet_r','width','flange_h','flange_t','bore']:
                    save_data[k] /= 10.0
                save_settings(save_data)
                
            raw_params['pld'] = (tot - th) * 0.305
            create_advanced_pulley(raw_params)
        except:
            ui.messageBox('Error:\n' + traceback.format_exc())

class AdvancedPulleyCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            onExec = AdvancedPulleyExecuteHandler()
            cmd.execute.add(onExec)
            handlers.append(onExec)
            
            inputs = cmd.commandInputs
            
            # 저장된 설정 불러오기
            st = load_settings()
            
            g1 = inputs.addGroupCommandInput('belt_grp', '1. 벨트 사양')
            g1.children.addValueInput('pitch', '피치 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('pitch', 0.3)))
            g1.children.addValueInput('tooth_h', '이빨 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('tooth_h', 0.114)))
            g1.children.addValueInput('total_h', '벨트 전체 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('total_h', 0.21)))
            
            g2 = inputs.addGroupCommandInput('pulley_grp', '2. 풀리 설계')
            teeth_input = g2.children.addIntegerSliderCommandInput('teeth', '이빨 개수 (Z)', 10, 200, False)
            teeth_input.valueOne = st.get('teeth', 17)
            
            g2.children.addValueInput('clearance', '치형 공차 (Gap, mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('clearance', 0.02)))
            g2.children.addValueInput('fillet_r', '이빨 모서리 R값 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('fillet_r', 0.019)))
            g2.children.addValueInput('width', '풀리 폭 (Width, mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('width', 0.4)))
            
            g3 = inputs.addGroupCommandInput('acc_grp', '3. 부가 사양')
            g3.children.addValueInput('flange_h', '플랜지 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('flange_h', 0.1)))
            g3.children.addValueInput('flange_t', '플랜지 두께 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('flange_t', 0.1)))
            g3.children.addValueInput('bore', '보어 사이즈 (mm)', 'mm', adsk.core.ValueInput.createByReal(st.get('bore', 0.898)))
            
            # 입력값 저장 체크박스 - 세 번째 인자를 True(Boolean)로 수정
            save_val = st.get('save_settings', True)
            inputs.addBoolValueInput('save_settings', '마지막 입력값 기억하기', True, '', save_val)
        except:
            ui.messageBox('Failed to create command:\n' + traceback.format_exc())


def run(context):
    try:
        cmdDef = ui.commandDefinitions.addButtonDefinition(COMMAND_ID, COMMAND_NAME, COMMAND_DESCRIPTION, '')
        onC = AdvancedPulleyCreatedHandler(); cmdDef.commandCreated.add(onC); handlers.append(onC)
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.addCommand(cmdDef)
    except: ui.messageBox('Failed:\n' + traceback.format_exc())

def stop(context):
    try:
        ui.commandDefinitions.itemById(COMMAND_ID).deleteMe()
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.itemById(COMMAND_ID).deleteMe()
    except: pass
