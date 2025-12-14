from core.context import PipelineContext
from core.steps import (
    TextureTrapStep,
    CreaseStep,
    EmulsionShiftStep,
    DebrisStep,
    ScratchesStep,
    MicroDefectsStep,
    StainsStep,
    EmulsionDegradationStep,
    ComplexGrainStep,
    ColorCastStep,
    LuminanceGrainStep,
    BandingStep,
    BlurStep,
    MpegStep
)

def apply_full_pipeline(img, p):

    ctx = PipelineContext(img, p)

    pipeline_steps = [

        TextureTrapStep(group_key='grp_grain', prob_key=None, seed_key='grain'),

        CreaseStep(group_key='grp_geo', prob_key='crease_probability', seed_key='geometry'),
        EmulsionShiftStep(group_key='grp_geo', prob_key='emulsion_shift_probability', seed_key='geometry'),

        DebrisStep(group_key='grp_debris', prob_key='debris_probability', seed_key='debris'),

        ScratchesStep(group_key='grp_scratches', prob_key='scratches_probability', seed_key='scratches'),

        MicroDefectsStep(group_key='grp_debris', prob_key='micro_defects_probability', seed_key='micro'),

        StainsStep(group_key='grp_stains', prob_key=None, seed_key=None),

        EmulsionDegradationStep(group_key='grp_emul', prob_key='emulsion_degradation_probability', seed_key=None),

        ComplexGrainStep(group_key='grp_grain', prob_key=None, seed_key=None),

        ColorCastStep(group_key='grp_post', prob_key=None, seed_key=None),

        LuminanceGrainStep(group_key='grp_grain', prob_key=None, seed_key=None),

        BandingStep(group_key='grp_banding', prob_key='banding_probability', seed_key=None),

        BlurStep(group_key='grp_post', prob_key=None, seed_key=None),
        MpegStep(group_key='grp_post', prob_key='mpeg_probability', seed_key=None)
    ]

    for step in pipeline_steps:
        if step.should_run(ctx):
            step.process(ctx)

    return ctx.get_image(), ctx.stats
