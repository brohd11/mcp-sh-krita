# summary: set a property on many layers at once: layer set PROP VALUE [LAYER...]
# usage: layer set PROP VALUE [LAYER...]     prints each changed layer as JSON
# LAYERs are ids or DOC/Group/Layer paths, from arguments or stdin (e.g. from layers):
#   layers | jq -c 'select(.kind == "vectorlayer")' | layer set visible false
# PROPs:
#   name TEXT          visible BOOL          opacity 0-100         blending MODE (e.g. multiply, screen)
#   position X,Y       color_label 0-8       locked BOOL           alpha_locked BOOL
#   inherit_alpha BOOL collapsed BOOL
# The value is checked before any layer changes.
# Krita's blending mode ids (KoCompositeOpRegistry, Krita 5.3). setBlendingMode takes any
# string and draws an unknown one as normal, so values are checked against this list.
BLENDING = """normal erase in out alphadarken destination-in destination-atop xor or and nand nor
xnor implication not_implication converse not_converse plus minus add subtract inverse_subtract
diff multiply divide arc_tangent geometric_mean additive_subtractive negation modulo
modulo_continuous divisive_modulo divisive_modulo_continuous modulo_shift modulo_shift_continuous
equivalence allanon parallel grain_merge grain_extract exclusion hard_mix_hdr hard_mix_photoshop
hard_mix_softer_photoshop overlay behind greater hard_overlay_hdr interpolation marker darken burn
linear_burn gamma_dark shade_ifs_illusions fog_darken_ifs_illusions lighten dodge dodge_hdr
linear_dodge screen hard_light soft_light_ifs_illusions soft_light_pegtop_delphi soft_light
soft_light_svg gamma_light gamma_illumination vivid_light vivid_light_hdr flat_light pin_light
pnorm_a pnorm_b super_light tint_ifs_illusions fog_lighten_ifs_illusions luminosity_sai hue color
tint saturation inc_saturation dec_saturation luminize inc_luminosity dec_luminosity hue_hsv
color_hsv saturation_hsv inc_saturation_hsv dec_saturation_hsv inc_value dec_value hue_hsl
color_hsl saturation_hsl inc_saturation_hsl dec_saturation_hsl lightness inc_lightness
dec_lightness hue_hsi color_hsi saturation_hsi inc_saturation_hsi dec_saturation_hsi intensity
inc_intensity dec_intensity copy copy_red copy_green copy_blue tangent_normalmap colorize bumpmap
combine_normal dissolve reflect glow freeze heat glow_heat heat_glow reflect_freeze freeze_reflect
heat_glow_freeze_reflect_hybrid lambert_lighting lambert_lighting_gamma2.2""".split() + [
    "hard mix", "hard overlay", "interpolation 2x", "penumbra a", "penumbra b", "penumbra c",
    "penumbra d", "easy burn", "easy dodge", "linear light", "darker color", "lighter color",
    "pass through"]


def set_opacity(node, v):
    node.setOpacity(round(v * 255 / 100))


def set_position(node, xy):
    node.move(*xy)


SETTERS = {
    "name": lambda n, v: n.setName(v),
    "visible": lambda n, v: n.setVisible(v),
    "opacity": set_opacity,
    "blending": lambda n, v: n.setBlendingMode(v),
    "position": set_position,
    "color_label": lambda n, v: n.setColorLabel(v),
    "locked": lambda n, v: n.setLocked(v),
    "alpha_locked": lambda n, v: n.setAlphaLocked(v),
    "inherit_alpha": lambda n, v: n.setInheritAlpha(v),
    "collapsed": lambda n, v: n.setCollapsed(v),
}


def parse(prop, text):
    if prop in ("name", "blending"):
        return text
    if prop in ("visible", "locked", "alpha_locked", "inherit_alpha", "collapsed"):
        return parse_bool(text, prop)
    if prop == "opacity":
        return parse_number(text, prop, 0, 100)
    if prop == "color_label":
        return parse_number(text, prop, 0, 8, integer=True)
    if prop == "position":
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2 or not all(p.lstrip("-").isdigit() for p in parts):
            fail("position: %r is not X,Y in whole pixels" % text)
        return int(parts[0]), int(parts[1])


if not ARGS or ARGS[0] != "set":
    fail("usage: layer set PROP VALUE [LAYER...]")
if len(ARGS) < 3:
    fail("usage: layer set PROP VALUE [LAYER...]  (PROPs: %s)" % ", ".join(SETTERS))
prop = ARGS[1].replace("-", "_")
if prop not in SETTERS:
    fail("unknown property %r (PROPs: %s)%s" % (ARGS[1], ", ".join(SETTERS), did_you_mean(prop, list(SETTERS))))
value = parse(prop, ARGS[2])
nodes = targets(3)
if prop == "blending" and value not in BLENDING:
    fail("blending: %r is not a Krita blending mode id%s (e.g. normal, multiply, screen, overlay, add, darken, lighten, color, luminize, soft_light_svg)" % (value, did_you_mean(value, BLENDING)))

for node, _ in nodes:
    SETTERS[prop](node, value)
refresh([doc for _, doc in nodes])
for node, doc in nodes:
    emit({"id": node_id(node), "path": node_path(node, doc)})
