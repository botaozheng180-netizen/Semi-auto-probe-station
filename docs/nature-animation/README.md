# Nature transition preview v5

Open `transitions.html` for the interactive onboarding and workflow simulation. `preview.html` retains the six individual eight-frame actions and links to the new preview.

The new transparent `nature-transitions-v5.png` provides sit-to-stand and sit-to-rest poses, reversed for returning to sitting. Built-in image-generation prompt: eight isolated full-body Nature poses, four sit-to-stand and four sit-to-lie, same identity, floor baseline, correct four-limb anatomy and transparent gutters. Measured bounds and playback scale are in `animations-v5.json`, with a script copy in `flow-data.js` so the demo works directly from disk.

Flow: welcome → seated questions → guide stand/point/sit → seated watching → operation → success or attention → next/retry guidance, or seated idle after completion. Returning users and completed tours rest after ten seconds without pointer or keyboard activity. Questions, guidance and operations do not time out into rest. Clicking resting Nature plays the reverse lie-to-sit transition before showing the help input. Restart uses a cancellation token to prevent previous animation sequences from changing the new state. Barking is visual, not audio.

Validation: JavaScript syntax, frame bounds, and simulated welcome/questions, guide/watch, failure retry, all six successful stages, completion, and rest-to-help passed. This is an animation/interaction prototype; SAP events, AI routing and hardware are not connected. Generated transition keyframes still have shape variation; they are a first transition pass, not final smooth in-betweens.

## Previous revision notes

# Nature animation study v4

Current playback specification: `animations-v4.json`. Six actions each contain exactly eight frame entries with image source, measured rectangle, scale, jump offset and duration. The HTML embeds the same specification to support opening directly from disk.

Welcome repeats its four-frame wave. Guide adds four tail-wag poses. Success adds four happy-bark poses. Attention is replaced with alternating forepaw stomps then barking. Waiting stretches eight poses/holds across 25.35 seconds. Thinking appends the corrected former four-frame Attention sequence. Barking is visual only; no audio is included.

New artwork: `nature-extension-v4.png`, generated with the built-in image tool using Nature v2 as reference. Prompt: sixteen isolated transparent poses in four rows—pointing with alternating tail positions, happy barking, and eight sequential attention poses (left stomp, right stomp, bark, settle). A targeted edit corrected the second paw lift to the opposite foreleg. Existing approved artwork is reused for the other portions.

Validation: all 48 entries have clear source boundaries and fit the padded canvas; all six timing arrays contain eight positive durations; JavaScript syntax and canvas runtime smoke checks pass. This remains a keyframe prototype with visible style/shape variation between generated batches.

## Earlier design notes
# Nature animation study v4

Open `preview.html` for six playable animations, speed controls, pause/replay and light/dark/transparency backgrounds. Assets are a first keyframe pass, not smooth final animation or an installed SAP feature.

Current atlas: `nature-atlas-v2.png`, 1024 × 1536 RGBA. Four poses per action across six rows: welcome, guide, success, attention, waiting, thinking. The generated positions are not an exact grid. `frames-v2.json` records measured isolated source rectangles; the preview draws these onto a 320 × 320 canvas with generous margins and a common baseline. Success frames retain a jump offset. Never divide this atlas into uniform cells.

Revision 2 changes: smaller, separated figures; palm-facing welcome wave instead of pointing; removed extra planted welcome forepaw; made thinking hind foot visibly part of the rear haunch; restored visible far hind paw in the airborne success poses. Attention raised-paw anatomy is corrected by the v3 override. Added Next frame buttons for inspection. The original v1 atlas remains for comparison.

Validation: all 24 source rectangles have clear boundaries at the character alpha threshold and fit the padded canvas; preview JavaScript passes Node syntax checking. Four-keyframe artwork still has small shape variations and is not final smooth production animation.

## Agreed interaction specification for later integration

- First launch and pointer entry: welcome, then “New user?” with ✔ / ❌.
- No: “Good to have you back! Have a nice Test~”.
- Yes: “Want me to guide you through?” with ✔ / ❌. Declining dismisses the offer and returns to waiting.
- Accepting follows AutoFocus → FocusMap → LayoutMap → AutoTest. Guide gesture at each next step; orient pointing toward the relevant control.
- Success celebrations follow successful autofocus, focus plane calibration, image stitching, layout mapping, single device test and auto device test. Errors/failures use attention.
- Default: lying waiting animation, with occasional head turn or sniff.
- Click Nature: “How can I help you?” and an input box. Submitting routes to AI Agent; thinking lasts while the answer is being prepared.
- Future event handling should keep hover from interrupting an active question, tour or pending answer. Hover welcome should trigger on pointer entry rather than every mouse movement.

## Generation provenance

Built-in image generation, using the approved Nature concept as the identity reference. Prompt: create a transparent 4-column × 6-row atlas, one consistent full-body corgi per cell, sequential welcome / guide / success / attention / waiting / thinking poses, bold charcoal outlines, orange-and-cream markings, gold medallion and two cream collar beads, no labels or motion marks. Each raised forepaw replaces a grounded foreleg. A targeted edit preserved layout and corrected the standing guide limb count, requesting fully transparent surroundings.

The source atlas is preserved directly from the generation tool. The preview animates grid cells without repainting the generated artwork. No application or hardware behavior has been changed.

Revision 2 generation prompt: preserve Nature identity and all six action rows, reduce figures to leave broad transparent gutters, use exactly two forelegs and two hind legs, wave with palm toward viewer and elbow bent, expose both hind paws in jumping frames, and distinguish seated hind feet from planted forelegs. Targeted follow-up removed the extra planted welcome paw and turned the thinking hind foot outward. Built-in image generation was used; runtime canvas framing changes only presentation, not the source artwork.

Attention revision 3: built-in image-generation edit removed the extra grounded right foreleg in Attention poses 2 and 3. Only the Attention row is used from nature-attention-v3.png; all other actions retain v2 artwork. Exact source rectangles are in frames-v2.json overrides. Verified all four corrected frame boundaries are clear and fit the padded canvas.
