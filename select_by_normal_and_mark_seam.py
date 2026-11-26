bl_info = {
    "name": "Xelias的快捷按键",
    "author": "CodeBuddy",
    "version": (1, 5),
    "blender": (2, 80, 0),
    "location": "View3D > 侧边栏 > 工具",
    "description": "选择当前面并按法线标记缝合线，并可按相机反射角定位灯光",
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}

import bpy
import bmesh
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix
import math
import re


class OBJECT_OT_add_linear_color_custom_property(bpy.types.Operator):
    """给选中对象添加 color 自定义属性"""
    bl_idname = "object.add_linear_color_custom_property"
    bl_label = "添加 color 属性"
    bl_description = "给选中对象添加 Float Array / Linear Color / 长度 3 的 color 自定义属性"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        selected_objects = context.selected_objects

        if not selected_objects:
            self.report({'WARNING'}, "请先选择对象/实例")
            return {'CANCELLED'}

        for obj in selected_objects:
            obj["color"] = [1.0, 1.0, 1.0]

            ui = obj.id_properties_ui("color")
            ui.update(
                min=0.0,
                max=1.0,
                soft_min=0.0,
                soft_max=1.0,
                step=0.1,
                precision=3,
                subtype='COLOR',
                description=""
            )

        self.report({'INFO'}, "已添加 color 自定义属性")
        return {'FINISHED'}


class OBJECT_OT_clear_selected_vertex_groups(bpy.types.Operator):
    """清除所选网格对象的全部顶点组"""
    bl_idname = "object.clear_selected_vertex_groups"
    bl_label = "清除所选顶点组"
    bl_description = "清除当前选中网格对象的全部顶点组；不会删除模型或骨骼修改器"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        mesh_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        group_count = sum(len(obj.vertex_groups) for obj in mesh_objects)

        for obj in mesh_objects:
            obj.vertex_groups.clear()

        self.report(
            {'INFO'},
            f"已清除 {len(mesh_objects)} 个模型的 {group_count} 个顶点组"
        )
        return {'FINISHED'}


class OBJECT_OT_make_selected_meshes_single_user(bpy.types.Operator):
    """为选中的网格对象创建独立 Mesh 数据"""
    bl_idname = "object.make_selected_meshes_single_user"
    bl_label = "独立化选中网格"
    bl_description = "复制选中对象的多用户 Mesh 数据，避免应用修改器时出现“无法应用一个多用户”错误"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' and obj.data for obj in context.selected_objects)

    def execute(self, context):
        mesh_objects = [
            obj for obj in context.selected_objects
            if obj.type == 'MESH' and obj.data
        ]
        shared_objects = [obj for obj in mesh_objects if obj.data.users > 1]

        for obj in shared_objects:
            obj.data = obj.data.copy()

        if shared_objects:
            self.report(
                {'INFO'},
                f"已独立化 {len(shared_objects)} 个对象的 Mesh 数据"
            )
        else:
            self.report({'INFO'}, "选中的网格已经都是单用户数据")

        return {'FINISHED'}


class FILE_OT_clean_missing_resources(bpy.types.Operator):
    """清理找不到文件的外部资源"""
    bl_idname = "file.clean_missing_resources"
    bl_label = "清理丢失资源"
    bl_description = "删除找不到文件且未打包的贴图，解决保存时“无法打包文件”的报错（不改变自动打包设置）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os
        removed = []
        for img in list(bpy.data.images):
            if img.packed_file or img.source not in {'FILE', 'SEQUENCE', 'TILED'}:
                continue
            path = bpy.path.abspath(img.filepath)
            if not path or not os.path.exists(path):
                removed.append(img.name)
                bpy.data.images.remove(img)

        if removed:
            print("已清理丢失资源:", removed)
            self.report({'INFO'}, f"已清理 {len(removed)} 个丢失贴图")
        else:
            self.report({'INFO'}, "没有发现丢失贴图")
        return {'FINISHED'}


class SCENE_OT_create_camera_timeline_markers(bpy.types.Operator):
    """按相机名称的自然顺序创建时间轴标记"""
    bl_idname = "scene.create_camera_timeline_markers"
    bl_label = "按相机创建标记"
    bl_description = "按相机名称自然排序（例如 1、2、10），设置帧范围并重建相机标记"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        cameras = []
        seen = set()

        def natural_sort_key(name):
            return [
                (1, int(part)) if part.isdigit() else (0, part.casefold())
                for part in re.split(r'(\d+)', name)
            ]

        def collect_cameras(collection):
            for obj in collection.objects:
                if obj.type == 'CAMERA' and obj.name not in seen:
                    cameras.append(obj)
                    seen.add(obj.name)
            for child in collection.children:
                collect_cameras(child)

        collect_cameras(scene.collection)
        cameras.sort(key=lambda camera: natural_sort_key(camera.name))

        if not cameras:
            self.report({'WARNING'}, "当前场景没有相机，未修改帧范围和标记")
            return {'CANCELLED'}

        for marker in list(scene.timeline_markers):
            scene.timeline_markers.remove(marker)

        scene.frame_start = 1
        scene.frame_end = len(cameras)

        for frame, camera in enumerate(cameras, start=1):
            marker = scene.timeline_markers.new(name=camera.name, frame=frame)
            marker.camera = camera

        self.report({'INFO'}, f"已为 {len(cameras)} 个相机设置帧范围和时间轴标记")
        return {'FINISHED'}


def _get_camera_position(context):
    """优先使用场景相机，否则回退到当前 3D 视口相机位置。"""
    scene_camera = context.scene.camera
    if scene_camera is not None:
        return scene_camera.matrix_world.translation.copy(), 'SCENE'

    rv3d = context.region_data
    if rv3d is not None:
        return rv3d.view_matrix.inverted().translation.copy(), 'VIEWPORT'

    return None, None


def _get_selected_light(context):
    active = context.active_object
    if active is not None and active.type == 'LIGHT':
        return active
    for obj in context.selected_objects:
        if obj.type == 'LIGHT':
            return obj
    return None


def _get_selected_mesh(context, exclude=None):
    exclude = exclude or set()
    active = context.active_object
    if active is not None and active.type == 'MESH' and active not in exclude:
        return active
    for obj in context.selected_objects:
        if obj.type == 'MESH' and obj not in exclude:
            return obj
    return None


def _object_world_bbox_center(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return sum(corners, Vector((0.0, 0.0, 0.0))) / 8.0


def _vec_angle_deg(a, b):
    if a.length_squared < 1e-16 or b.length_squared < 1e-16:
        return 180.0
    cosine = max(-1.0, min(1.0, a.normalized().dot(b.normalized())))
    return math.degrees(math.acos(cosine))


def _aim_light_minus_z(light_obj, direction):
    """让灯光的 -Z 轴朝向 direction。"""
    if direction.length_squared < 1e-12:
        return
    quat = direction.normalized().to_track_quat('-Z', 'Y')
    mode = light_obj.rotation_mode
    if mode == 'QUATERNION':
        light_obj.rotation_quaternion = quat
    elif mode == 'AXIS_ANGLE':
        axis, angle = quat.to_axis_angle()
        light_obj.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
    else:
        light_obj.rotation_euler = quat.to_euler(mode)


def _normal_matrix(obj):
    try:
        return obj.matrix_world.inverted_safe().to_3x3().transposed()
    except Exception:
        return obj.matrix_world.to_3x3()


def _ray_cast_mesh(context, obj, world_origin, world_direction):
    """对指定网格做物体空间射线检测，返回世界坐标命中点与世界法线。"""
    if obj is None or obj.type != 'MESH':
        return None

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    if eval_obj is None:
        eval_obj = obj

    mw = eval_obj.matrix_world
    try:
        inv = mw.inverted_safe()
    except Exception:
        return None

    direction = world_direction.copy()
    if direction.length_squared < 1e-16:
        return None
    direction.normalize()

    origin_local = inv @ world_origin
    dir_local = inv.to_3x3() @ direction
    if dir_local.length_squared < 1e-16:
        return None
    dir_local.normalize()

    result, location, normal, index = eval_obj.ray_cast(origin_local, dir_local)
    if not result:
        return None

    hit_world = mw @ location
    n_world = _normal_matrix(eval_obj) @ normal
    if n_world.length_squared < 1e-16:
        return None
    n_world.normalize()
    return hit_world, n_world, index, obj


def _same_object(a, b):
    if a is None or b is None:
        return False
    if a == b:
        return True
    src_a = getattr(a, "original", a)
    src_b = getattr(b, "original", b)
    return src_a == src_b or src_a.name == src_b.name


def _scene_ray_cast(context, world_origin, world_direction, only_obj=None):
    depsgraph = context.evaluated_depsgraph_get()
    direction = world_direction.copy()
    if direction.length_squared < 1e-16:
        return None
    direction.normalize()
    origin = world_origin + direction * 1e-5
    result, location, normal, index, obj, _matrix = context.scene.ray_cast(
        depsgraph, origin, direction
    )
    if not result or obj is None or obj.type != 'MESH':
        return None
    if only_obj is not None and not _same_object(obj, only_obj):
        return None
    if normal.length_squared < 1e-16:
        return None
    return location.copy(), normal.normalized(), index, obj


def _best_visible_face_hit(obj, cam_pos):
    """射线未命中时，改用朝向相机的真实面法线，绝不用“朝向相机”的假法线。"""
    if obj is None or obj.type != 'MESH' or not obj.data:
        return None

    mw = obj.matrix_world
    nmat = _normal_matrix(obj)
    center = _object_world_bbox_center(obj)
    view_dir = center - cam_pos
    if view_dir.length_squared < 1e-16:
        return None
    view_dir.normalize()

    best = None
    best_key = None
    for poly in obj.data.polygons:
        face_center = mw @ poly.center
        normal = nmat @ poly.normal
        if normal.length_squared < 1e-16:
            continue
        normal.normalize()
        to_cam = cam_pos - face_center
        if to_cam.length_squared < 1e-16:
            continue
        facing = normal.dot(to_cam.normalized())
        if facing <= 1e-5:
            continue

        denom = view_dir.dot(normal)
        if abs(denom) < 1e-8:
            hit = face_center
            t = (face_center - cam_pos).length
            on_ray = False
        else:
            t = (face_center - cam_pos).dot(normal) / denom
            if t <= 1e-6:
                hit = face_center
                on_ray = False
            else:
                hit = cam_pos + view_dir * t
                on_ray = True

        lateral = (hit - face_center).length
        key = (0 if on_ray else 1, lateral, -facing)
        if best_key is None or key < best_key:
            best_key = key
            best = (hit, normal.copy(), poly.index, obj)

    return best


def _resolve_surface_hit(context, cam_pos, mesh_obj=None, aim_point=None):
    """找到真实表面点及其真实世界法线。禁止用朝向相机的假法线兜底。"""
    aim = aim_point
    if aim is None and mesh_obj is not None:
        aim = _object_world_bbox_center(mesh_obj)
    if aim is None:
        aim = context.scene.cursor.location.copy()

    direction = aim - cam_pos
    if direction.length_squared < 1e-16:
        return None
    direction.normalize()

    hit = None
    source = None
    if mesh_obj is not None:
        hit = _ray_cast_mesh(context, mesh_obj, cam_pos, direction)
        source = "mesh_ray"
        if hit is None:
            hit = _scene_ray_cast(context, cam_pos, direction, only_obj=mesh_obj)
            source = "scene_ray_target"
        if hit is None:
            hit = _best_visible_face_hit(mesh_obj, cam_pos)
            source = "visible_face"
    else:
        hit = _scene_ray_cast(context, cam_pos, direction, only_obj=None)
        source = "scene_ray_cursor"

    if hit is None:
        return None

    loc, normal, index, obj = hit
    return {
        "hit_loc": loc,
        "hit_normal": normal,
        "hit_index": index,
        "hit_object": obj,
        "source": source,
    }


def _camera_right_up(context, cam_pos, hit_loc):
    cam = context.scene.camera if context is not None else None
    if cam is not None:
        rot = cam.matrix_world.to_3x3()
        right = rot @ Vector((1.0, 0.0, 0.0))
        up = rot @ Vector((0.0, 1.0, 0.0))
        if right.length_squared > 1e-12 and up.length_squared > 1e-12:
            return right.normalized(), up.normalized()

    view = hit_loc - cam_pos
    if view.length_squared < 1e-16:
        return Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))
    view.normalize()
    up = Vector((0.0, 0.0, 1.0))
    if abs(view.dot(up)) > 0.9:
        up = Vector((0.0, 1.0, 0.0))
    right = view.cross(up)
    if right.length_squared < 1e-16:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(view).normalized()
    return right, up


def _reflection_blocks_camera(cam_pos, hit_loc, light_loc, r_dir, min_angle_deg=30.0):
    back_to_cam = cam_pos - hit_loc
    angle = _vec_angle_deg(r_dir, back_to_cam)
    cam_to_hit = hit_loc - cam_pos
    if cam_to_hit.length_squared < 1e-16:
        return True, angle

    t = (light_loc - cam_pos).dot(cam_to_hit) / cam_to_hit.length_squared
    closest = cam_pos + cam_to_hit * t
    dist_line = (light_loc - closest).length
    if angle < min_angle_deg:
        return True, angle
    if 0.0 < t < 1.0 and dist_line < max(0.15, 0.2 * cam_to_hit.length):
        return True, angle
    return False, angle


def _offset_reflection_from_camera(context, cam_pos, hit_loc, normal, min_angle_deg=35.0):
    """把灯光从镜头前方偏到侧前方，避免挡住画面。"""
    back_to_cam = cam_pos - hit_loc
    if back_to_cam.length_squared < 1e-16:
        return None, 0.0
    back_to_cam.normalize()
    right, up = _camera_right_up(context, cam_pos, hit_loc)

    theta = math.radians(min_angle_deg)
    lift = math.radians(12.0)

    def make_dir(side):
        candidate = (
            back_to_cam * math.cos(theta)
            + side * math.sin(theta)
            + up * math.sin(lift)
        )
        if candidate.length_squared < 1e-16:
            return None
        candidate.normalize()
        return candidate

    candidate = make_dir(right)
    if candidate is None or candidate.dot(normal) <= 0.05:
        candidate = make_dir(-right)
    if candidate is None or candidate.dot(normal) <= 0.0:
        rot = Matrix.Rotation(theta, 3, normal)
        candidate = rot @ back_to_cam
        if candidate.length_squared < 1e-16 or candidate.dot(normal) <= 0.0:
            return None, 0.0
        candidate.normalize()
    return candidate, min_angle_deg


def _compute_reflection_placement(context, cam_pos, hit_loc, hit_normal, distance, avoid_camera=True):
    incident = hit_loc - cam_pos
    if incident.length_squared < 1e-12:
        return None
    incident.normalize()

    normal = hit_normal.normalized()
    if normal.length_squared < 1e-12:
        return None
    if normal.dot(-incident) < 0.0:
        normal = -normal

    reflection = incident - (2.0 * incident.dot(normal)) * normal
    if reflection.length_squared < 1e-12:
        return None
    reflection.normalize()

    offset_applied = False
    offset_angle = 0.0
    light_loc = hit_loc + reflection * distance
    if avoid_camera and context is not None:
        blocks, _angle = _reflection_blocks_camera(cam_pos, hit_loc, light_loc, reflection)
        if blocks:
            new_r, offset_angle = _offset_reflection_from_camera(
                context, cam_pos, hit_loc, normal
            )
            if new_r is not None:
                reflection = new_r
                light_loc = hit_loc + reflection * distance
                offset_applied = True

    return {
        "location": light_loc,
        "reflection": reflection,
        "normal": normal,
        "incident": incident,
        "offset_applied": offset_applied,
        "offset_angle": offset_angle,
    }


def _place_light_by_reflection(
    light_obj, cam_pos, hit_loc, hit_normal, distance, context=None, avoid_camera=True
):
    """按反射定律把灯光放到反射方向上，并朝向反射点。靠近镜头时自动偏置。"""
    info = _compute_reflection_placement(
        context, cam_pos, hit_loc, hit_normal, distance, avoid_camera=avoid_camera
    )
    if not info:
        return False, None
    light_obj.location = info["location"]
    _aim_light_minus_z(light_obj, -info["reflection"])
    return True, info


def _resolve_light_distance(light_obj, hit_loc, default=2.0, min_dist=0.2, max_dist=50.0):
    current = (light_obj.matrix_world.translation - hit_loc).length
    if min_dist <= current <= max_dist:
        return current
    return default


def _create_area_light(context, name="反射面光"):
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.size = 1.0
    light_data.energy = 100.0
    light_obj = bpy.data.objects.new(name, light_data)

    collection = context.collection or context.scene.collection
    collection.objects.link(light_obj)

    for obj in list(context.selected_objects):
        obj.select_set(False)
    light_obj.select_set(True)
    context.view_layer.objects.active = light_obj
    return light_obj


def _raycast_from_mouse(context, event):
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None

    coord = (float(event.mouse_region_x), float(event.mouse_region_y))
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    if origin is None or direction is None:
        return None

    hit = _scene_ray_cast(context, origin, direction, only_obj=None)
    if hit is None:
        return None
    location, normal, _index, obj = hit
    return location, normal, obj


def _restore_object_selection(context, selected_names, active_name):
    view_objects = context.view_layer.objects
    for obj in view_objects:
        obj.select_set(obj.name in selected_names)
    if active_name and active_name in view_objects:
        context.view_layer.objects.active = view_objects[active_name]


class LIGHT_OT_place_reflection_light(bpy.types.Operator):
    """在物体表面交互定位相机反射角灯光"""
    bl_idname = "light.place_reflection_light"
    bl_label = "相机反射定位灯光"
    bl_description = "鼠标在物体表面移动时，将灯光摆到对应相机的反射角位置；滚轮调距离，[ ] 调面光尺寸"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        space = context.space_data
        if space is None or space.type != 'VIEW_3D' or context.region_data is None:
            self.report({'WARNING'}, "请在 3D 视口中使用此功能")
            return {'CANCELLED'}

        cam_pos, cam_source = _get_camera_position(context)
        if cam_pos is None:
            self.report({'WARNING'}, "找不到相机位置，请先设置场景相机或在 3D 视口中操作")
            return {'CANCELLED'}

        self._area = context.area
        self._cam_source = cam_source
        self._cam_pos = cam_pos
        self._cleaned = False
        self._created_light = False
        self._has_hit = False
        self._distance_initialized = False
        self._last_hit_loc = None
        self._last_hit_normal = None
        self._distance = 2.0
        self._offset_applied = False
        self._orig_selected_names = [obj.name for obj in context.selected_objects]
        self._orig_active_name = (
            context.view_layer.objects.active.name
            if context.view_layer.objects.active is not None
            else None
        )

        light_obj = _get_selected_light(context)
        if light_obj is None:
            light_obj = _create_area_light(context)
            self._created_light = True

        self._light_obj = light_obj
        self._orig_location = light_obj.location.copy()
        self._orig_rotation_mode = light_obj.rotation_mode
        self._orig_rotation_euler = light_obj.rotation_euler.copy()
        self._orig_rotation_quaternion = light_obj.rotation_quaternion.copy()
        self._orig_rotation_axis_angle = tuple(light_obj.rotation_axis_angle)
        self._orig_size = light_obj.data.size if light_obj.data.type == 'AREA' else None

        self._apply_mouse_hit(context, event)
        self._update_header(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _clear_header(self, context):
        area = getattr(self, "_area", None) or (context.area if context else None)
        if area is not None:
            try:
                area.header_text_set(None)
            except Exception:
                pass

    def _update_header(self, context):
        area = getattr(self, "_area", None) or (context.area if context else None)
        if area is None:
            return
        light_obj = getattr(self, "_light_obj", None)
        if light_obj is not None and light_obj.data and light_obj.data.type == 'AREA':
            size_hint = f" | [ ]调尺寸({light_obj.data.size:.2f})"
        else:
            size_hint = " | [ ]调尺寸"
        offset_hint = " | 已偏置避开镜头" if getattr(self, "_offset_applied", False) else ""
        area.header_text_set(
            f"相机反射定位 | 左键确认 | 右键/ESC取消 | 滚轮调距离({self._distance:.2f}m){size_hint}{offset_hint}"
        )

    def _refresh_camera_position(self, context):
        # 场景相机保持固定；视口回退时跟随当前视角
        if getattr(self, "_cam_source", None) == 'VIEWPORT':
            cam_pos, cam_source = _get_camera_position(context)
            if cam_pos is not None:
                self._cam_pos = cam_pos
                self._cam_source = cam_source

    def _apply_hit(self, context, hit_loc, hit_normal, initialize_distance=False):
        light_obj = self._light_obj
        if light_obj is None:
            return False

        if initialize_distance and not self._created_light and not self._distance_initialized:
            self._distance = _resolve_light_distance(light_obj, hit_loc)
            self._distance_initialized = True
        elif not self._distance_initialized:
            self._distance_initialized = True

        ok, info = _place_light_by_reflection(
            light_obj, self._cam_pos, hit_loc, hit_normal, self._distance, context=context
        )
        if not ok:
            return False

        self._has_hit = True
        self._last_hit_loc = hit_loc
        self._last_hit_normal = hit_normal
        self._offset_applied = bool(info and info.get("offset_applied"))
        if context.area:
            context.area.tag_redraw()
        return True

    def _apply_mouse_hit(self, context, event):
        self._refresh_camera_position(context)
        hit = _raycast_from_mouse(context, event)
        if hit is None:
            return False
        hit_loc, hit_normal, _obj = hit
        return self._apply_hit(
            context, hit_loc, hit_normal, initialize_distance=True
        )

    def _reapply_last_hit(self, context):
        if not self._has_hit or self._last_hit_loc is None:
            return False
        self._refresh_camera_position(context)
        return self._apply_hit(context, self._last_hit_loc, self._last_hit_normal)

    def _restore_or_delete_light(self, context):
        if self._cleaned:
            return
        self._cleaned = True

        light_obj = getattr(self, "_light_obj", None)
        if light_obj is None:
            return

        if self._created_light:
            light_data = light_obj.data
            try:
                bpy.data.objects.remove(light_obj, do_unlink=True)
            except ReferenceError:
                pass
            if light_data is not None:
                try:
                    if light_data.users == 0:
                        bpy.data.lights.remove(light_data)
                except ReferenceError:
                    pass
            self._light_obj = None
            _restore_object_selection(
                context, self._orig_selected_names, self._orig_active_name
            )
            return

        if light_obj.name not in context.scene.objects:
            return

        light_obj.location = self._orig_location
        light_obj.rotation_mode = self._orig_rotation_mode
        light_obj.rotation_euler = self._orig_rotation_euler
        light_obj.rotation_quaternion = self._orig_rotation_quaternion
        light_obj.rotation_axis_angle = self._orig_rotation_axis_angle
        if self._orig_size is not None and light_obj.data.type == 'AREA':
            light_obj.data.size = self._orig_size

    def modal(self, context, event):
        try:
            if event.type == 'MOUSEMOVE':
                self._apply_mouse_hit(context, event)
                self._update_header(context)
                return {'RUNNING_MODAL'}

            if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
                factor = 1.05 if event.shift else 1.1
                if event.type == 'WHEELUPMOUSE':
                    self._distance *= factor
                else:
                    self._distance /= factor
                self._distance = max(0.05, min(200.0, self._distance))
                self._reapply_last_hit(context)
                self._update_header(context)
                return {'RUNNING_MODAL'}

            if event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
                light_obj = self._light_obj
                if light_obj is not None and light_obj.data.type == 'AREA':
                    if event.type == 'LEFT_BRACKET':
                        light_obj.data.size *= 0.9
                    else:
                        light_obj.data.size *= 1.1
                    light_obj.data.size = max(0.01, min(50.0, light_obj.data.size))
                    if context.area:
                        context.area.tag_redraw()
                self._update_header(context)
                return {'RUNNING_MODAL'}

            if event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
                if not self._has_hit:
                    self.report({'WARNING'}, "请先将鼠标指向物体表面")
                    self._update_header(context)
                    return {'RUNNING_MODAL'}
                self._cleaned = True
                self._clear_header(context)
                self.report({'INFO'}, f"已按反射角放置灯光，距离 {self._distance:.2f}m")
                return {'FINISHED'}

            if event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
                self._restore_or_delete_light(context)
                self._clear_header(context)
                self.report({'INFO'}, "已取消反射灯光定位")
                return {'CANCELLED'}

            # 保留中键/触控板视角操作，方便边看边摆灯
            if event.type in {
                'MIDDLEMOUSE',
                'INBETWEEN_MOUSEMOVE',
                'TRACKPADPAN',
                'TRACKPADZOOM',
                'MOUSEROTATE',
                'MOUSEPAN',
                'NDOF_MOTION',
            }:
                return {'PASS_THROUGH'}

            return {'RUNNING_MODAL'}
        except Exception as exc:
            self._restore_or_delete_light(context)
            self._clear_header(context)
            self.report({'ERROR'}, f"反射定位出错: {exc}")
            return {'CANCELLED'}

    def cancel(self, context):
        self._restore_or_delete_light(context)
        self._clear_header(context)


class LIGHT_OT_align_reflection_to_target(bpy.types.Operator):
    """将灯光一键对齐到相机相对目标的反射角"""
    bl_idname = "light.align_reflection_to_target"
    bl_label = "一键对齐反射角"
    bl_description = "根据场景相机与选中网格（或 3D 游标处的表面）计算反射角；若反射方向会挡住镜头，会自动偏到侧前方"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _get_selected_light(context) is not None

    def execute(self, context):
        cam_pos, _cam_source = _get_camera_position(context)
        if cam_pos is None:
            self.report({'WARNING'}, "找不到相机位置，请先设置场景相机或在 3D 视口中操作")
            return {'CANCELLED'}

        light_obj = _get_selected_light(context)
        if light_obj is None:
            self.report({'WARNING'}, "请先选择一盏灯光")
            return {'CANCELLED'}

        mesh_obj = _get_selected_mesh(context, exclude={light_obj})
        if mesh_obj is not None:
            aim_point = _object_world_bbox_center(mesh_obj)
        else:
            aim_point = context.scene.cursor.location.copy()

        hit = _resolve_surface_hit(
            context, cam_pos, mesh_obj=mesh_obj, aim_point=aim_point
        )
        if hit is None:
            self.report(
                {'WARNING'},
                "没有打到物体表面，请同时选中目标网格，或把 3D 游标放到物体表面上"
            )
            return {'CANCELLED'}

        hit_loc = hit["hit_loc"]
        hit_normal = hit["hit_normal"]
        distance = _resolve_light_distance(light_obj, hit_loc)
        ok, info = _place_light_by_reflection(
            light_obj, cam_pos, hit_loc, hit_normal, distance, context=context
        )
        if not ok:
            self.report({'WARNING'}, "无法计算反射方向")
            return {'CANCELLED'}

        if context.area:
            context.area.tag_redraw()

        if info and info.get("offset_applied"):
            self.report(
                {'INFO'},
                f"已对齐反射角（反射方向靠近镜头，已自动偏置 {info['offset_angle']:.0f}°，避免挡住画面），距离 {distance:.2f}m"
            )
        else:
            self.report({'INFO'}, f"已将灯光对齐到反射角，距离 {distance:.2f}m")
        return {'FINISHED'}


class MESH_OT_select_by_normal_and_mark_seam(bpy.types.Operator):
    """选择相同法线面并标记缝合线"""
    bl_idname = "mesh.select_by_normal_and_mark_seam"
    bl_label = "选择相同法线面并标记缝合线"
    bl_options = {'REGISTER', 'UNDO'}
    
    angle_threshold: bpy.props.FloatProperty(
        name="法线角度阈值",
        description="判断法线相似的角度阈值（度）",
        default=5.0,
        min=0.0,
        max=180.0
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
    
    def invoke(self, context, event):
        # 从场景属性获取阈值
        self.angle_threshold = context.scene.normal_angle_threshold
        return self.execute(context)
    
    def execute(self, context):
        # 获取当前编辑模式下的网格
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        
        # 确保在面选择模式
        bpy.ops.mesh.select_mode(type='FACE')
        
        # 获取选中的面
        selected_faces = [f for f in bm.faces if f.select]
        
        if not selected_faces:
            self.report({'WARNING'}, "请先选择一个面")
            return {'CANCELLED'}
        
        # 获取第一个选中面的法线
        target_normal = selected_faces[0].normal.copy()
        
        # 清除当前选择
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # 重新选择第一个面
        selected_faces[0].select = True
        
        # 选择所有具有相似法线的面
        angle_threshold_rad = math.radians(self.angle_threshold)
        
        for face in bm.faces:
            if face.normal.dot(target_normal) > math.cos(angle_threshold_rad):
                face.select = True
        
        # 更新网格
        bmesh.update_edit_mesh(me)
        
        # 保存当前选择模式
        select_mode = []
        if tuple(bpy.context.tool_settings.mesh_select_mode) == (True, False, False):
            select_mode = 'VERT'
        elif tuple(bpy.context.tool_settings.mesh_select_mode) == (False, True, False):
            select_mode = 'EDGE'
        elif tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True):
            select_mode = 'FACE'
        
        # 选择边界边
        bpy.ops.mesh.region_to_loop()
        
        # 标记为缝合线
        bpy.ops.mesh.mark_seam(clear=False)
        
        # 恢复到面选择模式
        bpy.ops.mesh.select_mode(type='FACE')
        
        self.report({'INFO'}, "已选择相似法线面并标记边界为缝合线")
        return {'FINISHED'}

class VIEW3D_PT_select_by_normal_panel(bpy.types.Panel):
    """创建一个面板放置按钮"""
    bl_label = "Xelias"
    bl_idname = "VIEW3D_PT_select_by_normal_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "工具"
    
    def draw(self, context):
        layout = self.layout
        
        col = layout.column(align=True)
        col.label(text="选择并标记:")
        
        # 创建操作符并直接传递属性
        props = col.operator("mesh.select_by_normal_and_mark_seam")
        
        # 显示可调整的阈值
        col.prop(context.scene, "normal_angle_threshold")

        layout.separator()

        col = layout.column(align=True)
        col.label(text="网格数据:")
        col.operator(
            "object.make_selected_meshes_single_user",
            icon='MESH_DATA'
        )

        layout.separator()

        col = layout.column(align=True)
        col.label(text="自定义属性:")
        col.operator("object.add_linear_color_custom_property", icon='COLOR')

        layout.separator()

        col = layout.column(align=True)
        col.label(text="顶点组:")
        col.operator("object.clear_selected_vertex_groups", icon='GROUP_VERTEX')

        layout.separator()

        col = layout.column(align=True)
        col.label(text="文件:")
        col.operator("file.clean_missing_resources", icon='TRASH')

        layout.separator()
        col = layout.column(align=True)
        col.label(text="相机标记:")
        col.operator("scene.create_camera_timeline_markers", icon='MARKER')

        layout.separator()
        col = layout.column(align=True)
        col.label(text="相机反射灯光:")
        col.operator("light.place_reflection_light", icon='LIGHT_AREA')
        col.operator("light.align_reflection_to_target", icon='ORIENTATION_NORMAL')

# 当场景属性更新时的回调函数
def update_angle_threshold(self, context):
    # 这个函数在属性值改变时被调用
    pass

# 存储属性
def register_properties():
    bpy.types.Scene.normal_angle_threshold = bpy.props.FloatProperty(
        name="法线角度阈值",
        description="判断法线相似的角度阈值（度）",
        default=5.0,
        min=0.0,
        max=180.0,
        update=update_angle_threshold
    )

def unregister_properties():
    if hasattr(bpy.types.Scene, "normal_angle_threshold"):
        del bpy.types.Scene.normal_angle_threshold

# 注册和注销
classes = (
    OBJECT_OT_add_linear_color_custom_property,
    OBJECT_OT_clear_selected_vertex_groups,
    OBJECT_OT_make_selected_meshes_single_user,
    FILE_OT_clean_missing_resources,
    SCENE_OT_create_camera_timeline_markers,
    LIGHT_OT_place_reflection_light,
    LIGHT_OT_align_reflection_to_target,
    MESH_OT_select_by_normal_and_mark_seam,
    VIEW3D_PT_select_by_normal_panel,
)

def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()

if __name__ == "__main__":
    register()
