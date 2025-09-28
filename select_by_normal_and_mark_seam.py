bl_info = {
    "name": "选择相同法线面并标记缝合线",
    "author": "CodeBuddy",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > 侧边栏 > 工具",
    "description": "选择当前面，然后按法线选择所有相同法线面，然后选择区域轮廓线，最后标记缝合线",
    "warning": "",
    "doc_url": "",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector
import math

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
    bl_label = "法线选择工具"
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