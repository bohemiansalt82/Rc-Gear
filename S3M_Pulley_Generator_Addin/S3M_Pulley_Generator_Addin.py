import adsk.core
import adsk.fusion
import traceback
import math

# 전역 변수 설정
app = adsk.core.Application.get()
ui = app.userInterface
handlers = []

# 명령 관련 상수
COMMAND_ID = 'S3M_Pulley_Generator_Addin'
COMMAND_NAME = 'S3M Pulley Generator'
COMMAND_DESCRIPTION = '벨트에 맞는 정밀 S3M 타이밍 풀리를 생성합니다.'

def mm_to_cm(val): return val / 10.0

# --- 풀리 생성 핵심 로직 ---
def create_pulley(tooth_count, width_mm, flange_h_mm, flange_t_mm, bore_mm):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent
        
        # S3M 규격 고정수치
        pitch_mm = 3.0
        pld_mm = 0.38
        
        # 지름 계산
        pd_cm = mm_to_cm((tooth_count * pitch_mm) / math.pi)
        od_cm = pd_cm - mm_to_cm(pld_mm * 2)
        r_outer = od_cm / 2
        
        # 이빨 홈(Groove) 깊이 및 폭
        groove_depth = 1.14 # mm
        r_inner = r_outer - mm_to_cm(groove_depth)
        
        # 홈 형상 (사다리꼴 베이스)
        gap = 0.1 # 여유공간
        base_w_mm = 1.1 + gap # 입구쪽 폭
        tip_w_mm = 1.9 + gap  # 바닥쪽 폭
        
        angle_pitch = (2 * math.pi) / tooth_count
        angle_half_base = (mm_to_cm(base_w_mm) / 2) / r_outer
        angle_half_tip = (mm_to_cm(tip_w_mm) / 2) / r_inner
        
        # 1. 치형 포함 전체 프로파일 생성
        sketches = root_comp.sketches
        xy_plane = root_comp.xYConstructionPlane
        sketch = sketches.add(xy_plane)
        sketch.name = 'Pulley_Full_Profile'
        sketch.isComputeDeferred = True
        
        lines = sketch.sketchCurves.sketchLines
        arcs = sketch.sketchCurves.sketchArcs
        
        # 전체 치형 형상을 그리는 루프
        all_points = []
        for i in range(tooth_count):
            theta_center = i * angle_pitch
            
            # 홈의 4개 점 계산
            p1_angle = theta_center - angle_half_base
            p2_angle = theta_center - angle_half_tip
            p3_angle = theta_center + angle_half_tip
            p4_angle = theta_center + angle_half_base
            
            p1 = adsk.core.Point3D.create(r_outer * math.cos(p1_angle), r_outer * math.sin(p1_angle), 0)
            p2 = adsk.core.Point3D.create(r_inner * math.cos(p2_angle), r_inner * math.sin(p2_angle), 0)
            p3 = adsk.core.Point3D.create(r_inner * math.cos(p3_angle), r_inner * math.sin(p3_angle), 0)
            p4 = adsk.core.Point3D.create(r_outer * math.cos(p4_angle), r_outer * math.sin(p4_angle), 0)
            
            # 홈의 측면과 바닥면 그리기
            l1 = lines.addByTwoPoints(p1, p2)
            l2 = lines.addByTwoPoints(p2, p3)
            l3 = lines.addByTwoPoints(p3, p4)
            
            # 다음 이빨까지의 외곽 원호
            next_p1_angle = (i + 1) * angle_pitch - angle_half_base
            p_next_start = adsk.core.Point3D.create(r_outer * math.cos(next_p1_angle), r_outer * math.sin(next_p1_angle), 0)
            arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p4, p_next_start)
        
        sketch.isComputeDeferred = False
        
        # 2. 치형 구역 돌출
        prof = sketch.profiles.item(0)
        extrudes = root_comp.features.extrudeFeatures
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm_to_cm(width_mm)))
        pulley_feat = extrudes.add(ext_input)
        pulley_body = pulley_feat.bodies.item(0)
        
        # 3. 플랜지 생성 (양쪽)
        f_dia = od_cm + mm_to_cm(flange_h_mm * 2)
        
        # 아래쪽 플랜지
        sketch_f1 = sketches.add(xy_plane)
        sketch_f1.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), f_dia / 2)
        prof_f1 = sketch_f1.profiles.item(0)
        ext_f1_input = extrudes.createInput(prof_f1, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_f1_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-mm_to_cm(flange_t_mm)))
        extrudes.add(ext_f1_input)
        
        # 위쪽 플랜지 (Offset Plane 사용)
        planes = root_comp.constructionPlanes
        plane_input = planes.createInput()
        plane_input.setByOffset(xy_plane, adsk.core.ValueInput.createByReal(mm_to_cm(width_mm)))
        offset_plane = planes.add(plane_input)
        
        sketch_f2 = sketches.add(offset_plane)
        sketch_f2.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), f_dia / 2)
        prof_f2 = sketch_f2.profiles.item(0)
        ext_f2_input = extrudes.createInput(prof_f2, adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_f2_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm_to_cm(flange_t_mm)))
        extrudes.add(ext_f2_input)
        
        # 4. 관통 보어 생성 (중심 구멍)
        sketch_bore = sketches.add(xy_plane)
        sketch_bore.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), mm_to_cm(bore_mm) / 2)
        prof_bore = sketch_bore.profiles.item(0)
        ext_bore_input = extrudes.createInput(prof_bore, adsk.fusion.FeatureOperations.CutFeatureOperation)
        
        # 보어가 확실히 전체를 관통하도록 양방향으로 충분한 거리(Belt Width + Flange) 설정
        total_h_cm = mm_to_cm(width_mm + flange_t_mm * 4) # 넉넉하게 설정
        dist_input = adsk.core.ValueInput.createByReal(total_h_cm)
        ext_bore_input.setDistanceExtent(True, dist_input) # True = Symmetric
        extrudes.add(ext_bore_input)
        
        ui.messageBox(f'정밀 S3M 풀리가 생성되었습니다.\n이빨 개수: {tooth_count}T\n피치 지름: {pd_cm*10:.2f}mm')
        
    except:
        ui.messageBox('풀리 생성 실패:\n' + traceback.format_exc())

# --- 핸들러 클래스 ---
class PulleyExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        try:
            inputs = args.firingEvent.sender.commandInputs
            # Casting 사용하여 안전하게 값 추출
            z_input = adsk.core.IntegerSliderCommandInput.cast(inputs.itemById('teeth'))
            w_input = adsk.core.ValueCommandInput.cast(inputs.itemById('width'))
            fh_input = adsk.core.ValueCommandInput.cast(inputs.itemById('flange_h'))
            ft_input = adsk.core.ValueCommandInput.cast(inputs.itemById('flange_t'))
            bore_input = adsk.core.ValueCommandInput.cast(inputs.itemById('bore'))
            
            create_pulley(z_input.valueOne, w_input.value*10, fh_input.value*10, ft_input.value*10, bore_input.value*10)
        except:
            ui.messageBox('Notify 실패:\n' + traceback.format_exc())

class PulleyCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = PulleyExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
            
            inputs = cmd.commandInputs
            inputs.addIntegerSliderCommandInput('teeth', '이빨 개수 (Z)', 10, 200, False).valueOne = 24
            inputs.addValueInput('width', '벨트 폭 (W, mm)', 'mm', adsk.core.ValueInput.createByReal(1.2))
            inputs.addValueInput('flange_h', '플랜지 외경 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.2))
            inputs.addValueInput('flange_t', '플랜지 두께 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.15))
            inputs.addValueInput('bore', '중심 보어 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.8))
        except:
            ui.messageBox('Created 실패:\n' + traceback.format_exc())

# --- 시작 및 종료 ---
def run(context):
    try:
        cmdDef = ui.commandDefinitions.addButtonDefinition(COMMAND_ID, COMMAND_NAME, COMMAND_DESCRIPTION, '')
        onCreated = PulleyCreatedHandler()
        cmdDef.commandCreated.add(onCreated)
        handlers.append(onCreated)
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.addCommand(cmdDef)
    except:
        if ui: ui.messageBox('시작 실패:\n' + traceback.format_exc())

def stop(context):
    try:
        ui.commandDefinitions.itemById(COMMAND_ID).deleteMe()
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.itemById(COMMAND_ID).deleteMe()
    except: pass
