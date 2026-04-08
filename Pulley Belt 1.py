import adsk.core
import adsk.fusion
import traceback
import math

# STD 522 S3M 사다리꼴 + 라운딩(Fillet) 처리된 치형 벨트 생성 스크립트
# 특징: 각진 사다리꼴 형태에 미세한 라운딩을 추가하여 실제 벨트와 유사한 부드러운 형상 구현

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        
        if not design:
            ui.messageBox('Fusion 360 디자인 환경에서 실행해 주세요.')
            return

        # -----------------------------
        # 1. 파라미터 설정 (mm 단위)
        # -----------------------------
        pitch_mm = 3.0
        belt_length_mm = 522.0
        tooth_count = int(round(belt_length_mm / pitch_mm))
        
        belt_width_mm = 10.0
        tooth_height_mm = 1.14
        total_thickness_mm = 1.94
        pld_mm = 0.38
        
        # 사다리꼴 형상 치수
        tip_width_mm = 1.0     
        base_width_mm = 1.95    
        fillet_radius_mm = 0.2  # 라운딩 반지름 (0.2mm)
        
        # -----------------------------
        # 2. 계산 및 좌표 변환 (cm 단위)
        # -----------------------------
        def mm_to_cm(val): return val / 10.0
        
        rp = mm_to_cm(belt_length_mm / (2 * math.pi))
        r_land = rp - mm_to_cm(pld_mm)
        r_back = r_land + mm_to_cm(total_thickness_mm - tooth_height_mm)
        r_tip = r_land - mm_to_cm(tooth_height_mm)
        
        # -----------------------------
        # 3. 모델링 작업
        # -----------------------------
        root_comp = design.rootComponent
        comp = root_comp
        
        sketches = comp.sketches
        xy_plane = comp.xYConstructionPlane
        sketch = sketches.add(xy_plane)
        sketch.name = 'S3M_Rounded_Trapezoid'
        
        # 벨트 외곽선
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
        
        # --- 라운딩(Fillet) 추가 ---
        arcs = sketch.sketchCurves.sketchArcs
        # 이빨 끝(Tip) 양쪽 모서리 라운딩
        arcs.addFillet(l_side_left, p2, l_top, p2, mm_to_cm(fillet_radius_mm))
        arcs.addFillet(l_top, p3, l_side_right, p3, mm_to_cm(fillet_radius_mm))
        
        # 이선(Land) 연결 로직
        angle_pitch = (2 * math.pi) / tooth_count
        angle_half_base = mm_to_cm(base_width_mm / 2) / r_land
        
        next_angle = angle_pitch - angle_half_base
        p_next_start = adsk.core.Point3D.create(r_land * math.cos(next_angle), r_land * math.sin(next_angle), 0)
        
        arcs = sketch.sketchCurves.sketchArcs
        # 이빨 바닥면 평면 구간
        l_land = arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p4, p_next_start)
        
        # 바닥면(Root) 라운딩은 패턴 연결을 위해 생략하거나 아주 미세하게 적용 
        # (여기서는 이빨 상단만 적용해도 충분히 그럴싸함)
        
        # 부채꼴 폐곡선 만들기
        p_back_1 = adsk.core.Point3D.create(r_back * math.cos(angle_half_base), r_back * math.sin(angle_half_base), 0)
        p_back_2 = adsk.core.Point3D.create(r_back * math.cos(next_angle), r_back * math.sin(next_angle), 0)
        
        lines.addByTwoPoints(p1, p_back_1)
        lines.addByTwoPoints(p_next_start, p_back_2)
        arcs.addByCenterStartEnd(adsk.core.Point3D.create(0, 0, 0), p_back_2, p_back_1)
        
        # -----------------------------
        # 4. 돌출 및 패턴
        # -----------------------------
        prof = sketch.profiles.item(0)
        extrudes = comp.features.extrudeFeatures
        distance = adsk.core.ValueInput.createByReal(mm_to_cm(belt_width_mm))
        ext_input = extrudes.createInput(prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        ext_input.setDistanceExtent(False, distance)
        belt_segment = extrudes.add(ext_input)
        
        pattern_features = comp.features.circularPatternFeatures
        input_ents = adsk.core.ObjectCollection.create()
        input_ents.add(belt_segment)
        
        z_axis = comp.zConstructionAxis
        pattern_input = pattern_features.createInput(input_ents, z_axis)
        pattern_input.quantity = adsk.core.ValueInput.createByReal(tooth_count)
        pattern_input.totalAngle = adsk.core.ValueInput.createByString('360 deg')
        
        pattern_features.add(pattern_input)
        
        ui.messageBox(f'라운딩된 사다리꼴 벨트 생성이 완료되었습니다.\n라운딩 반경: {fillet_radius_mm}mm')

    except:
        if ui:
            ui.messageBox('실패:\n{}'.format(traceback.format_exc()))

if __name__ == '__main__':
    run(None)