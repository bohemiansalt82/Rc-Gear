import adsk.core
import adsk.fusion
import traceback
import math

# Advanced Timing Pulley Generator Add-in
# 벨트 스펙 기반 역계산 및 공차 자동 반영 기능 포함

app = adsk.core.Application.get()
ui = app.userInterface
handlers = []

COMMAND_ID = 'Advanced_Pulley_Generator'
COMMAND_NAME = 'Advanced Pulley Generator'
COMMAND_DESCRIPTION = '벨트 규격에 맞춘 정밀 타이밍 풀리 역설계 생성기'

def mm_to_cm(val): return val / 10.0

# --- 핵심 물리 로직: 벨트-풀리 역계산 ---
def create_advanced_pulley(params):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent
        
        # 입력 파라미터 추출
        z = params['teeth']
        pitch = params['pitch']
        tooth_h = params['tooth_h']
        pld = params['pld']
        clearance = params['clearance']
        width = params['width']
        f_h = params['flange_h']
        f_t = params['flange_t']
        bore = params['bore']
        shape_type = params['shape_type'] # 'Circular' or 'Trapezoidal'
        
        # 1. 지름 계산 (역계산의 핵심)
        pd_cm = mm_to_cm((z * pitch) / math.pi)
        # 피치 라인과 치상 외경 사이의 거리(PLD) 반영
        od_cm = pd_cm - mm_to_cm(pld * 2)
        r_outer = od_cm / 2
        
        # 2. 풀리 홈(Groove) 깊이 및 폭 계산
        # 벨트 이빨 높이보다 약간 깊게(공차)
        groove_depth_mm = tooth_h + 0.1
        r_inner = r_outer - mm_to_cm(groove_depth_mm)
        
        # 홈의 폭 (피치 라인에서의 폭 기준 공차 반영)
        # S-시리즈(STS/S8M 등)는 보통 피치의 약 60%가 이빨 폭
        # 사다리꼴은 보통 40~50%
        if shape_type == 'Circular':
            base_w_mm = (pitch * 0.6) + clearance
            tip_w_mm = (pitch * 0.4) + clearance
        else: # Trapezoidal
            base_w_mm = (pitch * 0.5) + clearance
            tip_w_mm = (pitch * 0.3) + clearance

        # 3. 통합 프로파일 생성
        sketches = root_comp.sketches
        xy_plane = root_comp.xYConstructionPlane
        sketch = sketches.add(xy_plane)
        sketch.name = f'Pulley_{z}T_{shape_type}'
        sketch.isComputeDeferred = True
        
        lines = sketch.sketchCurves.sketchLines
        arcs = sketch.sketchCurves.sketchArcs
        splines = sketch.sketchCurves.sketchFittedSplines
        
        angle_pitch = (2 * math.pi) / z
        angle_half_base = (mm_to_cm(base_w_mm) / 2) / r_outer
        angle_half_tip = (mm_to_cm(tip_w_mm) / 2) / r_inner
        
        for i in range(z):
            theta_center = i * angle_pitch
            
            p1_angle = theta_center - angle_half_base
            p2_angle = theta_center - angle_half_tip
            p3_angle = theta_center + angle_half_tip
            p4_angle = theta_center + angle_half_base
            
            p1 = adsk.core.Point3D.create(r_outer * math.cos(p1_angle), r_outer * math.sin(p1_angle), 0)
            p2 = adsk.core.Point3D.create(r_inner * math.cos(p2_angle), r_inner * math.sin(p2_angle), 0)
            p3 = adsk.core.Point3D.create(r_inner * math.cos(p3_angle), r_inner * math.sin(p3_angle), 0)
            p4 = adsk.core.Point3D.create(r_outer * math.cos(p4_angle), r_outer * math.sin(p4_angle), 0)
            
            if shape_type == 'Circular':
                # 원형 치형의 경우 부드러운 전이를 위해 스플라인 또는 3점 호 사용
                # 여기서는 S-시리즈 특유의 형상을 위해 중간점 추가하여 호 생성
                pm_left = adsk.core.Point3D.create((r_outer+r_inner)/2 * math.cos(p1_angle + (p2_angle-p1_angle)*0.2), (r_outer+r_inner)/2 * math.sin(p1_angle + (p2_angle-p1_angle)*0.2), 0)
                pm_right = adsk.core.Point3D.create((r_outer+r_inner)/2 * math.cos(p4_angle + (p3_angle-p4_angle)*0.2), (r_outer+r_inner)/2 * math.sin(p4_angle + (p3_angle-p4_angle)*0.2), 0)
                
                arcs.addByThreePoints(p1, pm_left, p2)
                lines.addByTwoPoints(p2, p3)
                arcs.addByThreePoints(p3, pm_right, p4)
            else:
                # 사다리꼴
                l1 = lines.addByTwoPoints(p1, p2)
                l2 = lines.addByTwoPoints(p2, p3)
                l3 = lines.addByTwoPoints(p3, p4)
                # 코너 라운딩 (경고 방지를 위해 짧은 선분에만 적용)
                if tip_w_mm > 0.5:
                    arcs.addFillet(l1, p2, l2, p2, mm_to_cm(0.1))
                    arcs.addFillet(l2, p3, l3, p3, mm_to_cm(0.1))
            
            # 랜드(Land) 구간
            next_p1_angle = (i + 1) * angle_pitch - angle_half_base
            p_next_start = adsk.core.Point3D.create(r_outer * math.cos(next_p1_angle), r_outer * math.sin(next_p1_angle), 0)
            arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p4, p_next_start)
            
        sketch.isComputeDeferred = False
        
        # 4. 피처 생성 (돌출, 플랜지, 보어)
        prof = sketch.profiles.item(0)
        extrudes = root_comp.features.extrudeFeatures
        
        # 메인 치성부
        ext_input_body = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input_body.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm_to_cm(width)))
        ext_body = extrudes.add(ext_input_body)
        
        # 플랜지
        f_dia = od_cm + mm_to_cm(f_h * 2)
        sk_f1 = sketches.add(xy_plane)
        sk_f1.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), f_dia / 2)
        ext_f1_input = extrudes.createInput(sk_f1.profiles.item(0), adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_f1_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(-mm_to_cm(f_t)))
        extrudes.add(ext_f1_input)
        
        # 반대쪽 플랜지용 Plane
        planes = root_comp.constructionPlanes
        p_input = planes.createInput()
        p_input.setByOffset(xy_plane, adsk.core.ValueInput.createByReal(mm_to_cm(width)))
        sk_f2 = sketches.add(planes.add(p_input))
        sk_f2.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), f_dia / 2)
        ext_f2_input = extrudes.createInput(sk_f2.profiles.item(0), adsk.fusion.FeatureOperations.JoinFeatureOperation)
        ext_f2_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm_to_cm(f_t)))
        extrudes.add(ext_f2_input)
        
        # 보어
        sk_bore = sketches.add(xy_plane)
        sk_bore.sketchCurves.sketchCircles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), mm_to_cm(bore) / 2)
        ext_bore = extrudes.createInput(sk_bore.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation)
        ext_bore.setDistanceExtent(True, adsk.core.ValueInput.createByReal(mm_to_cm(width + f_t * 5))) # 충분히 길게 관통
        extrudes.add(ext_bore)
        
        ui.messageBox(f'정밀 역계산 풀리 생성 완료\n타입: {shape_type}\n피치지름: {pd_cm*10:.2f}mm\n외경: {od_cm*10:.2f}mm')
        
    except:
        ui.messageBox('생성 실패:\n' + traceback.format_exc())

# --- UI 핸들러 ---
class AdvancedPulleyExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.firingEvent.sender.commandInputs
            
            pld_val = inputs.itemById('pld').value * 10
            pitch_val = inputs.itemById('pitch').value * 10
            
            # PLD 자동 계산 로직 (0 입력 시)
            if pld_val == 0:
                # S-시리즈 표준 근사치 적용
                pld_val = pitch_val * 0.085 # 8mm -> 0.68mm, 3mm -> 0.25mm
            
            params = {
                'shape_type': inputs.itemById('shape_type').selectedItem.name,
                'pitch': pitch_val,
                'tooth_h': inputs.itemById('tooth_h').value * 10,
                'pld': pld_val,
                'clearance': inputs.itemById('clearance').value * 10,
                'teeth': inputs.itemById('teeth').valueOne,
                'width': inputs.itemById('width').value * 10,
                'flange_h': inputs.itemById('flange_h').value * 10,
                'flange_t': inputs.itemById('flange_t').value * 10,
                'bore': inputs.itemById('bore').value * 10
            }
            create_advanced_pulley(params)
        except: ui.messageBox('Error:\n' + traceback.format_exc())

class AdvancedPulleyCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        cmd = args.command
        onExec = AdvancedPulleyExecuteHandler()
        cmd.execute.add(onExec); handlers.append(onExec)
        
        inputs = cmd.commandInputs
        
        # 1. 벨트 규격 그룹
        group1 = inputs.addGroupCommandInput('belt_grp', '1. 벨트 스펙 입력 (S8M 예시)')
        shape = group1.children.addDropDownCommandInput('shape_type', '치형 타입', adsk.core.DropDownStyles.TextListDropDownStyle)
        shape.listItems.add('Circular', True)
        shape.listItems.add('Trapezoidal', False)
        
        group1.children.addValueInput('pitch', '피치 (Pitch, mm)', 'mm', adsk.core.ValueInput.createByReal(0.8)) # 8mm
        group1.children.addValueInput('tooth_h', '이빨 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.305))
        pld_input = group1.children.addValueInput('pld', '피치라인 오프셋 (0=자동계산, mm)', 'mm', adsk.core.ValueInput.createByReal(0.0686))
        pld_input.tooltip = '모를 경우 0을 입력하면 피치에 맞춰 자동 계산됩니다.'
        
        # 2. 풀리 공차 및 설계 그룹
        group2 = inputs.addGroupCommandInput('pulley_grp', '2. 풀리 공차 및 설계')
        group2.children.addIntegerSliderCommandInput('teeth', '이빨 개수 (Z)', 10, 200, False).valueOne = 30
        group2.children.addValueInput('clearance', '치형 좌우 공차 (Gap, mm)', 'mm', adsk.core.ValueInput.createByReal(0.01))
        group2.children.addValueInput('width', '풀리 폭 (Width, mm)', 'mm', adsk.core.ValueInput.createByReal(2.5))
        
        # 3. 액세서리
        group3 = inputs.addGroupCommandInput('acc_grp', '3. 플랜지 및 보어')
        group3.children.addValueInput('flange_h', '플랜지 높이 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.3))
        group3.children.addValueInput('flange_t', '플랜지 두께 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.2))
        group3.children.addValueInput('bore', '보어 사이즈 (mm)', 'mm', adsk.core.ValueInput.createByReal(1.0))

def run(context):
    try:
        # 아이콘 리소스 경로 설정 (./resources)
        cmdDef = ui.commandDefinitions.addButtonDefinition(COMMAND_ID, COMMAND_NAME, COMMAND_DESCRIPTION, './resources')
        
        onCreated = AdvancedPulleyCreatedHandler()
        cmdDef.commandCreated.add(onCreated); handlers.append(onCreated)
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.addCommand(cmdDef)
    except: ui.messageBox('Failed:\n' + traceback.format_exc())

def stop(context):
    try:
        ui.commandDefinitions.itemById(COMMAND_ID).deleteMe()
        ui.allToolbarPanels.itemById('SolidCreatePanel').controls.itemById(COMMAND_ID).deleteMe()
    except: pass
