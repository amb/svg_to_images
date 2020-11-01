bl_info = {
    "name": "Import SVG as images",
    "author": "ambi",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "",
    "description": "Import SVG as images",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "https://github.com/amb/svg_to_images/issues",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

__version__ = ".".join(map(str, bl_info["version"]))

import bpy
import bmesh
import numpy as np
import mathutils as mu
import os
import ntpath
from bpy_extras.io_utils import ImportHelper

WAND_IMPORTED = False
try:
    from wand.api import library
    from wand.color import Color
    from wand.image import Image

    WAND_IMPORTED = True
except ImportError as e:
    print(e)


def add_material(name, image, sn_loc=[-400.0, 300.0]):
    if len(name) > 60:
        name = name[:60]
    if name not in bpy.data.materials.keys():
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        sn = mat.node_tree.nodes.new("ShaderNodeTexImage")
        sn.location = sn_loc

        # Connect base color
        bc = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
        mat.node_tree.links.new(sn.outputs["Color"], bc)

        # Connect alpha
        a = mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"]
        mat.node_tree.links.new(sn.outputs["Alpha"], a)
    else:
        mat = bpy.data.materials[name]

    mat.blend_method = 'BLEND'
    mat.shadow_method = 'CLIP'
    mat.node_tree.nodes["Image Texture"].image = image
    return mat


def load_svg_as_image_plane(filepath, dpi):
    infile = filepath
    image_name = "".join(ntpath.basename(filepath).split(".")[:-1])
    with Image(resolution=dpi) as image:
        # Load SVG
        with Color("transparent") as background_color:
            library.MagickSetBackgroundColor(image.wand, background_color.resource)

        # Convert SVG to image
        image.read(filename=infile, resolution=dpi)

        # Import image data into Blender
        array = np.array(image)
        print(array.shape)
        print(array.dtype)

        size = array.shape[1], array.shape[0]
        bpy_image = bpy.data.images.new(image_name, width=size[0], height=size[1])
        bpy_image.pixels = array.flatten()

        # Create new empty Bmesh in which to build our new textured quad
        bm = bmesh.new()

        # add vertices and uvs before creating the new face
        # ASSUMPTION: Blender units are set to 1 unit = 1 meter (SI)
        inch_to_meter = 0.0254
        w, h = size[0] * inch_to_meter / dpi, size[1] * inch_to_meter / dpi
        vertices = [(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)]
        uv_list = [(0, 1.0, 0), (1.0, 1.0, 0), (1.0, 0.0, 0), (0, 0.0, 0)]
        for vert in vertices:
            bm.verts.new((vert[0], vert[1], vert[2]))
        bm.faces.new((i for i in bm.verts))

        # add uvs to the new face
        uv_layer = bm.loops.layers.uv.verify()
        # bm.faces.layers.uv.verify()

        bm.faces.ensure_lookup_table()
        face = bm.faces[-1]
        # TODO: this here is bug
        face.material_index = 0
        for i, loop in enumerate(face.loops):
            uv = loop[uv_layer].uv
            uv[0] = uv_list[i][0]
            uv[1] = uv_list[i][1]

        # create mesh
        new_mesh = bpy.data.meshes.new(image_name)
        bm.to_mesh(new_mesh)
        bm.free()

        # make object from mesh
        new_object = bpy.data.objects.new(image_name, new_mesh)

        # assign material
        mat_id = add_material(image_name, bpy_image)
        new_object.data.materials.append(mat_id)

        # add object to scene collection
        bpy.context.scene.collection.objects.link(new_object)


class ImportSVGToImagesOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.svg_to_images"
    bl_label = "Import SVG to images"
    bl_description = "Import SVG to images"

    filter_glob: bpy.props.StringProperty(default="*.svg", options={"HIDDEN"})
    files: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    dpi: bpy.props.IntProperty(name="DPI", description="DPI", default=300, min=1)

    def execute(self, context):
        folder = os.path.dirname(self.filepath)
        # iterate through the selected files
        for j, i in enumerate(self.files):
            # generate full path to file
            path_to_file = os.path.join(folder, i.name)
            print("Opening file:", path_to_file)
            load_svg_as_image_plane(path_to_file, self.dpi)
        return {"FINISHED"}


class SVGTI_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def draw(self, context):
        global WAND_IMPORTED
        if WAND_IMPORTED == False:
            layout = self.layout
            row = layout.row()
            row.alert = True
            row.label(text="Wand library/ImageMagick not installed.")
            row = layout.row()
            row.label(text="https://imagemagick.org/script/download.php#windows")
        else:
            layout = self.layout
            row = layout.row()
            row.label(text="All libraries successfully imported.")


classes = (ImportSVGToImagesOperator, SVGTI_AddonPreferences)


def menu_func_import(self, context):
    self.layout.operator(ImportSVGToImagesOperator.bl_idname, text="SVG as images (.svg)")


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for c in classes[::-1]:
        bpy.utils.unregister_class(c)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
