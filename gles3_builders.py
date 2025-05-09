"""Functions used to generate source files during build time"""

import os.path

from methods import generated_wrapper, print_error, to_raw_cstring


class GLES3HeaderStruct:
    def __init__(self):
        self.vertex_lines = []
        self.fragment_lines = []
        self.uniforms = []
        self.fbos = []
        self.texunits = []
        self.texunit_names = []
        self.ubos = []
        self.ubo_names = []
        self.feedbacks = []

        self.vertex_included_files = []
        self.fragment_included_files = []

        self.reading = ""
        self.line_offset = 0
        self.vertex_offset = 0
        self.fragment_offset = 0
        self.variant_defines = []
        self.variant_names = []
        self.specialization_names = []
        self.specialization_values = []


def include_file_in_gles3_header(filename: str, header_data: GLES3HeaderStruct, depth: int):
    with open(filename, "r", encoding="utf-8") as fs:
        line = fs.readline()

        while line:
            if line.find("=") != -1 and header_data.reading == "":
                # Mode
                eqpos = line.find("=")
                defname = line[:eqpos].strip().upper()
                define = line[eqpos + 1 :].strip()
                header_data.variant_names.append(defname)
                header_data.variant_defines.append(define)
                line = fs.readline()
                header_data.line_offset += 1
                header_data.vertex_offset = header_data.line_offset
                continue

            if line.find("=") != -1 and header_data.reading == "specializations":
                # Specialization
                eqpos = line.find("=")
                specname = line[:eqpos].strip()
                specvalue = line[eqpos + 1 :]
                header_data.specialization_names.append(specname)
                header_data.specialization_values.append(specvalue)
                line = fs.readline()
                header_data.line_offset += 1
                header_data.vertex_offset = header_data.line_offset
                continue

            if line.find("#[modes]") != -1:
                # Nothing really, just skip
                line = fs.readline()
                header_data.line_offset += 1
                header_data.vertex_offset = header_data.line_offset
                continue

            if line.find("#[specializations]") != -1:
                header_data.reading = "specializations"
                line = fs.readline()
                header_data.line_offset += 1
                header_data.vertex_offset = header_data.line_offset
                continue

            if line.find("#[vertex]") != -1:
                header_data.reading = "vertex"
                line = fs.readline()
                header_data.line_offset += 1
                header_data.vertex_offset = header_data.line_offset
                continue

            if line.find("#[fragment]") != -1:
                header_data.reading = "fragment"
                line = fs.readline()
                header_data.line_offset += 1
                header_data.fragment_offset = header_data.line_offset
                continue

            while line.find("#include ") != -1:
                includeline = line.replace("#include ", "").strip()[1:-1]

                included_file = os.path.relpath(os.path.dirname(filename) + "/" + includeline)
                if included_file not in header_data.vertex_included_files and header_data.reading == "vertex":
                    header_data.vertex_included_files += [included_file]
                    if include_file_in_gles3_header(included_file, header_data, depth + 1) is None:
                        print_error(f'In file "{filename}": #include "{includeline}" could not be found!"')
                elif included_file not in header_data.fragment_included_files and header_data.reading == "fragment":
                    header_data.fragment_included_files += [included_file]
                    if include_file_in_gles3_header(included_file, header_data, depth + 1) is None:
                        print_error(f'In file "{filename}": #include "{includeline}" could not be found!"')

                line = fs.readline()

            if line.find("uniform") != -1 and line.lower().find("texunit:") != -1:
                # texture unit
                texunitstr = line[line.find(":") + 1 :].strip()
                if texunitstr == "auto":
                    texunit = "-1"
                else:
                    texunit = str(int(texunitstr))
                uline = line[: line.lower().find("//")]
                uline = uline.replace("uniform", "")
                uline = uline.replace("highp", "")
                uline = uline.replace(";", "")
                lines = uline.split(",")
                for x in lines:
                    x = x.strip()
                    x = x[x.rfind(" ") + 1 :]
                    if x.find("[") != -1:
                        # unfiorm array
                        x = x[: x.find("[")]

                    if x not in header_data.texunit_names:
                        header_data.texunits += [(x, texunit)]
                        header_data.texunit_names += [x]

            elif line.find("uniform") != -1 and line.lower().find("ubo:") != -1:
                # uniform buffer object
                ubostr = line[line.find(":") + 1 :].strip()
                ubo = str(int(ubostr))
                uline = line[: line.lower().find("//")]
                uline = uline[uline.find("uniform") + len("uniform") :]
                uline = uline.replace("highp", "")
                uline = uline.replace(";", "")
                uline = uline.replace("{", "").strip()
                lines = uline.split(",")
                for x in lines:
                    x = x.strip()
                    x = x[x.rfind(" ") + 1 :]
                    if x.find("[") != -1:
                        # unfiorm array
                        x = x[: x.find("[")]

                    if x not in header_data.ubo_names:
                        header_data.ubos += [(x, ubo)]
                        header_data.ubo_names += [x]

            elif line.find("uniform") != -1 and line.find("{") == -1 and line.find(";") != -1:
                uline = line.replace("uniform", "")
                uline = uline.replace(";", "")
                lines = uline.split(",")
                for x in lines:
                    x = x.strip()
                    x = x[x.rfind(" ") + 1 :]
                    if x.find("[") != -1:
                        # unfiorm array
                        x = x[: x.find("[")]

                    if x not in header_data.uniforms:
                        header_data.uniforms += [x]

            if (line.strip().find("out ") == 0 or line.strip().find("flat ") == 0) and line.find("tfb:") != -1:
                uline = line.replace("flat ", "")
                uline = uline.replace("out ", "")
                uline = uline.replace("highp ", "")
                uline = uline.replace(";", "")
                uline = uline[uline.find(" ") :].strip()

                if uline.find("//") != -1:
                    name, bind = uline.split("//")
                    if bind.find("tfb:") != -1:
                        name = name.strip()
                        bind = bind.replace("tfb:", "").strip()
                        header_data.feedbacks += [(name, bind)]

            line = line.replace("\r", "")
            line = line.replace("\n", "")

            if header_data.reading == "vertex":
                header_data.vertex_lines += [line]
            if header_data.reading == "fragment":
                header_data.fragment_lines += [line]

            line = fs.readline()
            header_data.line_offset += 1

    return header_data


def build_gles3_header(filename: str, shader: str) -> None:
    include_file_in_gles3_header(shader, header_data := GLES3HeaderStruct(), 0)
    out_file_class = (
        os.path.basename(shader).replace(".glsl", "").title().replace("_", "").replace(".", "") + "ShaderGLES3"
    )

    with generated_wrapper(filename) as file:
        defspec = 0
        defvariant = ""

        file.write(f"""\
#include "drivers/gles3/shader_gles3.h"

class {out_file_class} : public ShaderGLES3 {{
public:
""")

        if header_data.uniforms:
            uniforms = ",\n\t\t".join(uniform.upper() for uniform in header_data.uniforms)
            file.write(f"""\
	enum Uniforms {{
		{uniforms},
	}};

""")

        if header_data.variant_names:
            variant_names = ",\n\t\t".join(name for name in header_data.variant_names)
        else:
            variant_names = "DEFAULT"
            defvariant = " = DEFAULT"
        file.write(f"""\
	enum ShaderVariant {{
		{variant_names},
	}};

""")

        if header_data.specialization_names:
            specialization_names = ",\n\t\t".join(
                f"{name.upper()} = {1 << index}" for index, name in enumerate(header_data.specialization_names)
            )
            file.write(f"""\
	enum Specializations {{
		{specialization_names},
	}};

""")
        for index, specialization_value in enumerate(header_data.specialization_values):
            if specialization_value.strip().upper() in ["TRUE", "1"]:
                defspec |= 1 << index

        file.write(f"""\
	_FORCE_INLINE_ bool version_bind_shader(RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		return _version_bind_shader(p_version, p_variant, p_specialization);
	}}

""")

        if header_data.uniforms:
            file.write(f"""\
	_FORCE_INLINE_ int version_get_uniform(Uniforms p_uniform, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		return _version_get_uniform(p_uniform, p_version, p_variant, p_specialization);
	}}

	/* clang-format off */
#define TRY_GET_UNIFORM(var_name) int var_name = version_get_uniform(p_uniform, p_version, p_variant, p_specialization); if (var_name < 0) return
	/* clang-format on */

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, double p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1f(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint8_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int8_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint16_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int16_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, uint32_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1ui(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, int32_t p_value, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform1i(uniform_location, p_value);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Color &p_color, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLfloat col[4] = {{ p_color.r, p_color.g, p_color.b, p_color.a }};
		glUniform4fv(uniform_location, 1, col);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector2 &p_vec2, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec2[2] = {{ float(p_vec2.x), float(p_vec2.y) }};
		glUniform2fv(uniform_location, 1, vec2);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Size2i &p_vec2, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLint vec2[2] = {{ GLint(p_vec2.x), GLint(p_vec2.y) }};
		glUniform2iv(uniform_location, 1, vec2);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector3 &p_vec3, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec3[3] = {{ float(p_vec3.x), float(p_vec3.y), float(p_vec3.z) }};
		glUniform3fv(uniform_location, 1, vec3);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Vector4 &p_vec4, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLfloat vec4[4] = {{ float(p_vec4.x), float(p_vec4.y), float(p_vec4.z), float(p_vec4.w) }};
		glUniform4fv(uniform_location, 1, vec4);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform2f(uniform_location, p_a, p_b);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform3f(uniform_location, p_a, p_b, p_c);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, float p_a, float p_b, float p_c, float p_d, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		glUniform4f(uniform_location, p_a, p_b, p_c, p_d);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform3D &p_transform, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		const Transform3D &tr = p_transform;

		GLfloat matrix[16] = {{ /* build a 16x16 matrix */
			(GLfloat)tr.basis.rows[0][0],
			(GLfloat)tr.basis.rows[1][0],
			(GLfloat)tr.basis.rows[2][0],
			(GLfloat)0,
			(GLfloat)tr.basis.rows[0][1],
			(GLfloat)tr.basis.rows[1][1],
			(GLfloat)tr.basis.rows[2][1],
			(GLfloat)0,
			(GLfloat)tr.basis.rows[0][2],
			(GLfloat)tr.basis.rows[1][2],
			(GLfloat)tr.basis.rows[2][2],
			(GLfloat)0,
			(GLfloat)tr.origin.x,
			(GLfloat)tr.origin.y,
			(GLfloat)tr.origin.z,
			(GLfloat)1
		}};

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Transform2D &p_transform, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		const Transform2D &tr = p_transform;

		GLfloat matrix[16] = {{ /* build a 16x16 matrix */
			(GLfloat)tr.columns[0][0],
			(GLfloat)tr.columns[0][1],
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)tr.columns[1][0],
			(GLfloat)tr.columns[1][1],
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)0,
			(GLfloat)1,
			(GLfloat)0,
			(GLfloat)tr.columns[2][0],
			(GLfloat)tr.columns[2][1],
			(GLfloat)0,
			(GLfloat)1
		}};

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}}

	_FORCE_INLINE_ void version_set_uniform(Uniforms p_uniform, const Projection &p_matrix, RID p_version, ShaderVariant p_variant{defvariant}, uint64_t p_specialization = {defspec}) {{
		TRY_GET_UNIFORM(uniform_location);
		GLfloat matrix[16];

		for (int i = 0; i < 4; i++) {{
			for (int j = 0; j < 4; j++) {{
				matrix[i * 4 + j] = p_matrix.columns[i][j];
			}}
		}}

		glUniformMatrix4fv(uniform_location, 1, false, matrix);
	}}

#undef TRY_GET_UNIFORM

""")

        file.write("""\
protected:
	virtual void _init() override {
""")

        if header_data.uniforms:
            uniforms = ",\n\t\t\t".join(f'"{uniform}"' for uniform in header_data.uniforms)
            file.write(f"""\
		static const char *_uniform_strings[] = {{
			{uniforms}
		}};
""")
        else:
            file.write("""\
		static const char **_uniform_strings = nullptr;
""")

        if header_data.variant_defines:
            variant_count = len(header_data.variant_defines)
            variant_defines = ",\n\t\t\t".join(f'"{define}"' for define in header_data.variant_defines)
            file.write(f"""\
		static const char *_variant_defines[] = {{
			{variant_defines},
		}};
""")
        else:
            variant_count = 1
            file.write("""\
		static const char **_variant_defines[] = {" "};
""")

        if header_data.texunits:
            texunits = ",\n\t\t\t".join(f'{{ "{name}", {texunit} }}' for name, texunit in header_data.texunits)
            file.write(f"""\
		static TexUnitPair _texunit_pairs[] = {{
			{texunits},
		}};
""")
        else:
            file.write("""\
		static TexUnitPair *_texunit_pairs = nullptr;
""")

        if header_data.ubos:
            ubos = ",\n\t\t\t".join(f'{{ "{name}", {ubo} }}' for name, ubo in header_data.ubos)
            file.write(f"""\
		static UBOPair _ubo_pairs[] = {{
			{ubos},
		}};
""")
        else:
            file.write("""\
		static UBOPair *_ubo_pairs = nullptr;
""")

        if header_data.specialization_names:
            specializations = ",\n\t\t\t".join(
                f'{{ "{name}", {"true" if header_data.specialization_values[index].strip().upper() in ["TRUE", "1"] else "false"} }}'
                for index, name in enumerate(header_data.specialization_names)
            )
            file.write(f"""\
		static Specialization _spec_pairs[] = {{
			{specializations},
		}};
""")
        else:
            file.write("""\
		static Specialization *_spec_pairs = nullptr;
""")

        if header_data.feedbacks:
            feedbacks = ",\n\t\t\t".join(
                f'{{ "{name}", {0 if spec not in header_data.specialization_names else (1 << header_data.specialization_names.index(spec))} }}'
                for name, spec in header_data.feedbacks
            )
            file.write(f"""\
		static const Feedback _feedbacks[] = {{
			{feedbacks},
		}};
""")
        else:
            file.write("""\
		static const Feedback *_feedbacks = nullptr;
""")

        file.write(f"""\
		static const char _vertex_code[] = {{
{to_raw_cstring(header_data.vertex_lines)}
		}};

		static const char _fragment_code[] = {{
{to_raw_cstring(header_data.fragment_lines)}
		}};

		_setup(_vertex_code, _fragment_code, "{out_file_class}",
				{len(header_data.uniforms)}, _uniform_strings, {len(header_data.ubos)}, _ubo_pairs,
				{len(header_data.feedbacks)}, _feedbacks, {len(header_data.texunits)}, _texunit_pairs,
				{len(header_data.specialization_names)}, _spec_pairs, {variant_count}, _variant_defines);
	}}
}};
""")


def build_gles3_headers(target, source, env):
    env.NoCache(target)
    for src in source:
        build_gles3_header(f"{src}.gen.h", str(src))
