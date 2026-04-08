import adsk.core
import adsk.fusion
import traceback
import math

# 전역 변수 설정
app = adsk.core.Application.get()
ui = app.userInterface
handlers = []

# 명령 관련 상수
COMMAND_ID = 'S3M_Belt_Generator_Addin'
COMMAND_NAME = 'S3M Belt Generator'
COMMAND_DESCRIPTION = '정밀 S3M 타이밍 벨트를 생성합니다.'

# --- 벨트 생성 핵심 로직 ---
def create_belt(belt_length_mm, pitch_mm, belt_width_mm):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        root_comp = design.rootComponent
        
        tooth_count = int(round(belt_length_mm / pitch_mm))
        tooth_height_mm = 1.14
        total_thickness_mm = 1.94
        pld_mm = 0.38
        
        tip_width_mm = 1.0     
        base_width_mm = 1.95    
        fillet_radius_mm = 0.2  

        def mm_to_cm(val): return val / 10.0
        
        rp = mm_to_cm(belt_length_mm / (2 * math.pi))
        r_land = rp - mm_to_cm(pld_mm)
        r_back = r_land + mm_to_cm(total_thickness_mm - tooth_height_mm)
        r_tip = r_land - mm_to_cm(tooth_height_mm)
        
        sketches = root_comp.sketches
        xy_plane = root_comp.xYConstructionPlane
        sketch = sketches.add(xy_plane)
        sketch.name = f'S3M_Belt_{belt_length_mm}mm'
        
        circles = sketch.sketchCurves.sketchCircles
        circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r_back)
        
        def get_radial_pt(x_mm, y_mm):
            local_r = r_land - mm_to_cm(y_mm)
            angle = mm_to_cm(x_mm) / r_land
            return adsk.core.Point3D.create(local_r * math.cos(angle), local_r * math.sin(angle), 0)
        
        p1 = get_radial_pt(-base_width_mm / 2, 0)
        p2 = get_radial_pt(-tip_width_mm / 2, tooth_height_mm)
        p3 = get_radial_pt(tip_width_mm / 2, tooth_height_mm)
        p4 = get_radial_pt(base_width_mm / 2, 0)
        
        lines = sketch.sketchCurves.sketchLines
        l_side_left = lines.addByTwoPoints(p1, p2)
        l_top = lines.addByTwoPoints(p2, p3)
        l_side_right = lines.addByTwoPoints(p3, p4)
        
        arcs = sketch.sketchCurves.sketchArcs
        arcs.addFillet(l_side_left, p2, l_top, p2, mm_to_cm(fillet_radius_mm))
        arcs.addFillet(l_top, p3, l_side_right, p3, mm_to_cm(fillet_radius_mm))
        
        angle_pitch = (2 * math.pi) / tooth_count
        angle_half_base = mm_to_cm(base_width_mm / 2) / r_land
        next_angle = angle_pitch - angle_half_base
        p_next_start = adsk.core.Point3D.create(r_land * math.cos(next_angle), r_land * math.sin(next_angle), 0)
        
        arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p4, p_next_start)
        
        p_back_1 = adsk.core.Point3D.create(r_back * math.cos(angle_half_base), r_back * math.sin(angle_half_base), 0)
        p_back_2 = adsk.core.Point3D.create(r_back * math.cos(next_angle), r_back * math.sin(next_angle), 0)
        
        lines.addByTwoPoints(p1, p_back_1)
        lines.addByTwoPoints(p_next_start, p_back_2)
        arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p_back_2, p_back_1)
        
        prof = sketch.profiles.item(0)
        extrudes = root_comp.features.extrudeFeatures
        distance = adsk.core.ValueInput.createByReal(mm_to_cm(belt_width_mm))
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, distance)
        belt_segment = extrudes.add(ext_input)
        
        pattern_features = root_comp.features.circularPatternFeatures
        input_ents = adsk.core.ObjectCollection.create()
        input_ents.add(belt_segment)
        
        z_axis = root_comp.zConstructionAxis
        pattern_input = pattern_features.createInput(input_ents, z_axis)
        pattern_input.quantity = adsk.core.ValueInput.createByReal(tooth_count)
        pattern_input.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        pattern_features.add(pattern_input)
        
        ui.messageBox(f'성공: {belt_length_mm}mm 벨트 생성이 완료되었습니다.')
    except:
        ui.messageBox('벨트 생성 중 오류 발생:\n' + traceback.format_exc())

# --- 이벤트 핸들러 클래스 ---
class BeltCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            command = args.firingEvent.sender
            inputs = command.commandInputs
            
            length = inputs.itemById('belt_length').value
            pitch = inputs.itemById('pitch').value
            width = inputs.itemById('belt_width').value
            
            create_belt(length * 10, pitch * 10, width * 10) # cm to mm
        except:
            ui.messageBox('명령 실행 실패:\n' + traceback.format_exc())

class BeltCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = BeltCommandExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
            
            inputs = cmd.commandInputs
            
            # 입력 항목 추가
            inputs.addValueInput('belt_length', '벨트 길이 (mm)', 'mm', adsk.core.ValueInput.createByReal(52.2))
            inputs.addValueInput('pitch', '피치 (mm)', 'mm', adsk.core.ValueInput.createByReal(0.3))
            inputs.addValueInput('belt_width', '벨트 폭 (mm)', 'mm', adsk.core.ValueInput.createByReal(1.0))
            
        except:
            ui.messageBox('명령 생성 실패:\n' + traceback.format_exc())

# --- Add-in 시작 및 종료 ---
def run(context):
    try:
        # 명령 정의 추가
        cmdDef = ui.commandDefinitions.addButtonDefinition(COMMAND_ID, COMMAND_NAME, COMMAND_DESCRIPTION, '')
        
        onCommandCreated = BeltCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        handlers.append(onCommandCreated)
        
        # UI에 버튼 추가 (SOLID -> CREATE 패널 하단)
        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
        createPanel.controls.addCommand(cmdDef)
        
    except:
        if ui:
            ui.messageBox('Add-in 시작 실패:\n' + traceback.format_exc())

def stop(context):
    try:
        # UI 요소 제거
        objDir = ui.commandDefinitions.itemById(COMMAND_ID)
        if objDir:
            objDir.deleteMe()
            
        createPanel = ui.allToolbarPanels.itemById('SolidCreatePanel')
        cntrl = createPanel.controls.itemById(COMMAND_ID)
        if cntrl:
            cntrl.deleteMe()
    except:
        if ui:
            ui.messageBox('Add-in 종료 실패:\n' + traceback.format_exc())
