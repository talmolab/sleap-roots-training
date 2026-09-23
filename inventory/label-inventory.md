# Label inventory

What labels files exist beneath the scanned root, and what is in them. Every
path is emitted relative to the root, which appears as `<ROOT>`.

## Coverage

- `.slp` files seen: 18099
- candidates: 850
- excluded, derived filename: 16626
- excluded, derived directory: 623
- directories that could not be read: 0
- families: 656

## Skeleton table

Analysed 76 of 656 families. A family is analysed only where
species, root type, mode and a node count are all derivable; the rest are
counted below, not silently dropped.

- not analysed: 522 no-mode, 10 no-node-count, 146 no-root-type, 3 no-species

### Rows selected by more than one capture mode

- `(arabidopsis, primary, age: null)` is selected by cylinder, plate, whose files carry 6, 7, 8 nodes. One row cannot describe both.

### Species with no row

- covercress
- medicago
- pennycress
- sorghum
- wheat

Derivation is open by design, so a crop nobody has heard of is not
hidden — which means directory names that are not crops also land here.
These are **not** species; they are tokens read off a path:

- circumnutation, cropping, multiple, packages, pest, shoots

### Skeleton names the existing check cannot resolve

- Skeleton-0 — 255 file(s): `<ROOT>/20250102_generalizability_experiment/lateral/arabidopsis/labels_arabidopsis_lateral_4nodes.v010.pkg.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/arabidopsis/labels_arabidopsis_lateral_4nodes.v010.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/canola/labels_ONLYcanola_lateral_3nodes.v000.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/canola/labels_canola_lateral_3nodes.v014.pkg.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/canola/labels_canola_lateral_3nodes.v014.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/pennycress/labels_ONLYpennycress_lateral_3nodes.v000.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/sorghum/sorghum_lateral_roots_4nodes_labels.v001.pkg.slp`, `<ROOT>/20250102_generalizability_experiment/lateral/sorghum/sorghum_lateral_roots_4nodes_labels.v001.slp`, and 247 more
- Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0, Skeleton-0 — 1 file(s): `<ROOT>/SLEAP_Rice/10_do/main_root/FN2021/FN2021_20frames.v002.slp`
- Skeleton-1 — 309 file(s): `<ROOT>/20241107_generalizability_exp/primary/sorghum/labels_sorghum_5-12DAG_primary_6nodes.v008.pkg.slp`, `<ROOT>/20241107_generalizability_exp/primary/sorghum/labels_sorghum_5-12DAG_primary_6nodes.v008.slp`, `<ROOT>/20250102_generalizability_experiment/primary/arabidopsis/labels_ONLYarabidopsis_primary_6nodes.v000.slp`, `<ROOT>/20250102_generalizability_experiment/primary/arabidopsis/labels_canola_pennycress_arabidopsis.v015.pkg.slp`, `<ROOT>/20250102_generalizability_experiment/primary/arabidopsis/labels_canola_pennycress_arabidopsis.v015.slp`, `<ROOT>/20250102_generalizability_experiment/primary/canola/labels_ONLYcanola_primary_6nodes.v000.slp`, `<ROOT>/20250102_generalizability_experiment/primary/canola/labels_canola_pennycress_primary_6nodes.v000.slp`, `<ROOT>/20250102_generalizability_experiment/primary/canola/labels_canola_primary_6nodes.v005.pkg.slp`, and 301 more
- Skeleton-10 — 5 file(s): `<ROOT>/SLEAP_medicago_plates/combined_roots/MK24_tertiary_combined.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK31_tertiary_combined.slp`, `<ROOT>/SLEAP_medicago_plates/tertiary/tertiary_root_MK22_Day14_labels.v003.pkg.slp`, `<ROOT>/SLEAP_medicago_plates/tertiary/tertiary_root_MK22_Day14_labels.v003_updated_filenames.slp`, `<ROOT>/SLEAP_medicago_plates/tertiary/tertiary_root_MK22_Day14_labels.v004.slp`
- Skeleton-10, Skeleton-5 — 1 file(s): `<ROOT>/SLEAP_medicago_plates/combined_roots/MK22_tertiary_combined.slp`
- Skeleton-104 — 2 file(s): `<ROOT>/SLEAP_arabidopsis/lateral_root/3_nodes/labels.v002.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/3_nodes/labels_canola_pennycress_arabidopsis.v004.slp`
- Skeleton-12 — 1 file(s): `<ROOT>/SLEAP_sorghum/lateral_4nodes/labels(fast 6 Lateral).v002.slp`
- Skeleton-194 — 1 file(s): `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/labels.v001.slp`
- Skeleton-2 — 15 file(s): `<ROOT>/20250529_seminal_root_generalist/wheat/labels_sr_5-14DAG.v004.slp`, `<ROOT>/20250530_seminal_root_generalist/wheat/labels_sr_5-14DAG.v004.slp`, `<ROOT>/SLEAP_arabidopsis/adventitious_roots/labels_7DAP_adventitious.v002.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7_do/old_labels_juan_gonzalez/labels_7DAP_laterals_.v005.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7_do/old_labels_juan_gonzalez/labels_7DAP_laterals_ONLY.v008.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/7_do/labels_7DAP_laterals_.v005.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/7_do/labels_7DAP_laterals_ONLY.v007.slp`, `<ROOT>/SLEAP_arabidopsis/merged.01.slp`, and 7 more
- Skeleton-25 — 6 file(s): `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/javiers_labels.v001_6 nodes merged copy.slp`, `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/javiers_labels.v001_6 nodes merged.slp`, `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/javiers_labels.v001_6 nodes_11222023.slp`, `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/javiers_labels_6nodes.v002.slp`, `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/javiers_primary_labels_6nodes.v012.slp`, `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes/labels.v001_6 nodes merged.slp`
- Skeleton-3 — 7 file(s): `<ROOT>/SLEAP_Canola_Pennycress/primary_root/Canola_PrimaryRoot_V2.slp`, `<ROOT>/SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/primary_root/labels/day2and3 copy.slp`, `<ROOT>/SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/primary_root/labels/labels_wheat_2-3DAG.slp`, `<ROOT>/SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/primary_root/labels/labels_wheat_2-3DAG.v002.slp`, `<ROOT>/SLEAP_arabidopsis_plates/labels/primary_8nodes/labels_wheat_2-3DAG.slp`, `<ROOT>/SLEAP_arabidopsis_plates/labels/primary_8nodes/labels_wheat_2-3DAG.v002.slp`, `<ROOT>/SLEAP_sorghum/primary_6nodes/labels_D5_KE.v002.slp`
- Skeleton-31 — 5 file(s): `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do/javiers_labels.v002_4 nodes merged copy.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do/javiers_labels.v002_4 nodes merged.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do/javiers_labels.v002_4 nodes_11222023.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do/javiers_lateral_labels_4nodes.v005 - Copy.slp`, `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do/javiers_lateral_labels_4nodes.v010.slp`
- Skeleton-317 — 1 file(s): `<ROOT>/SLEAP_Soy/primary_multi-day/javiers_labels/labels.v001.slp`
- Skeleton-395 — 3 file(s): `<ROOT>/SLEAP_shoots/SLEAP_8262025_backup/updatedsmallremoved.slp`, `<ROOT>/SLEAP_shoots/updatedsmall copy.slp`, `<ROOT>/SLEAP_shoots/updatedsmall.slp`
- Skeleton-4 — 4 file(s): `<ROOT>/SLEAP_circumnutation/labels/exp1-sd1-sd1_plate003_labels_bihourly.slp`, `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/exp1-sd1-sd1/labels/plate003_labels_bihourly.slp`, `<ROOT>/SLEAP_covercress_plates/lateral/labels_lateral_2025-06-20_T3_day_11.v002.slp`, `<ROOT>/SLEAP_covercress_plates/lateral/labels_laterals_covercress_13DO_3nodes.v008.slp`
- Skeleton-5 — 11 file(s): `<ROOT>/20250717_plate_medicago_primary_sweep_receptive_field/primary_root_MK22_Day14_labels.v003.slp`, `<ROOT>/SLEAP_circumnutation/labels/exp2-sd1-tzt_plate002_labels_bihourly.slp`, `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/exp2-sd1-tzt/labels/plate002_labels_bihourly.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK22_primary_combined.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK24_primary_combined.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK31_primary_combined.slp`, `<ROOT>/SLEAP_medicago_plates/primary/primary_root_MK22_Day14_labels.v006.pkg.slp`, `<ROOT>/SLEAP_medicago_plates/primary/primary_root_MK22_Day14_labels.v006.slp`, and 3 more
- Skeleton-6 — 5 file(s): `<ROOT>/SLEAP_circumnutation/labels/exp1-sd1-sd1_plate004_labels_bihourly.slp`, `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/exp1-sd1-sd1/labels/plate004_labels_bihourly.slp`, `<ROOT>/SLEAP_medicago_plates/primary/primary_root_MK22_Day10_labels.v001.slp`, `<ROOT>/SLEAP_sorghum/primary_6nodes/labels.v001xt.slp`, `<ROOT>/primary/primary_root_MK22_Day10_labels.v001.slp`
- Skeleton-7 — 12 file(s): `<ROOT>/20250723_plate_medicago_lateral_sweep_receptive_field/lateral_root_MK22_Day14_3nodes_labels.v003.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK24_lateral_combined.slp`, `<ROOT>/SLEAP_medicago_plates/combined_roots/MK31_lateral_combined.slp`, `<ROOT>/SLEAP_medicago_plates/lateral/lateral_root_MK22_Day14_labels.v002.slp`, `<ROOT>/SLEAP_medicago_plates/lateral/lateral_root_MK22_Day14_labels_deleted_predicted_instances.v006.slp`, `<ROOT>/SLEAP_medicago_plates/lateral/lateral_root_MK22_Day14_labels_for_model_building.v004.pkg.slp`, `<ROOT>/SLEAP_medicago_plates/lateral/lateral_root_MK22_Day14_labels_for_model_building.v006_updated_paths.slp`, `<ROOT>/SLEAP_medicago_plates/lateral/lateral_root_MK22_Day14_labels_for_model_building.v007.slp`, and 4 more
- Skeleton-7, Skeleton-5 — 1 file(s): `<ROOT>/SLEAP_medicago_plates/combined_roots/MK22_lateral_combined.slp`
- Skeleton-89 — 1 file(s): `<ROOT>/SLEAP_Soy/lateral_root_4_nodes/javiers_lateral_labels.v001.slp`

## Directories holding more than one family

A directory is not a collection. This tool lists what it found and
**makes no determination** about which files form a collection, which
supersedes which, or which should be registered. A person reads this.

- `<ROOT>/20241107_generalizability_exp/primary/sorghum` holds 2 families: labels_sorghum_5-12DAG_primary_6nodes.v#, labels_sorghum_5-12DAG_primary_6nodes.v#
- `<ROOT>/20250102_generalizability_experiment/lateral/arabidopsis` holds 2 families: labels_arabidopsis_lateral_4nodes.v#, labels_arabidopsis_lateral_4nodes.v#
- `<ROOT>/20250102_generalizability_experiment/lateral/canola` holds 3 families: labels_ONLYcanola_lateral_3nodes.v#, labels_canola_lateral_3nodes.v#, labels_canola_lateral_3nodes.v#
- `<ROOT>/20250102_generalizability_experiment/lateral/sorghum` holds 2 families: sorghum_lateral_roots_4nodes_labels.v#, sorghum_lateral_roots_4nodes_labels.v#
- `<ROOT>/20250102_generalizability_experiment/lateral/soybean` holds 2 families: labels_soy_lateral_4nodes.v#, labels_soy_lateral_4nodes.v#
- `<ROOT>/20250102_generalizability_experiment/primary/arabidopsis` holds 3 families: labels_ONLYarabidopsis_primary_6nodes.v#, labels_canola_pennycress_arabidopsis.v#, labels_canola_pennycress_arabidopsis.v#
- `<ROOT>/20250102_generalizability_experiment/primary/canola` holds 4 families: labels_ONLYcanola_primary_6nodes.v#, labels_canola_pennycress_primary_6nodes.v#, labels_canola_primary_6nodes.v#, labels_canola_primary_6nodes.v#
- `<ROOT>/20250102_generalizability_experiment/primary/sorghum` holds 2 families: labels_sorghum_5-12DAG_primary_6nodes.v#, labels_sorghum_5-12DAG_primary_6nodes.v#
- `<ROOT>/20250102_generalizability_experiment/primary/soybean` holds 2 families: labels_soybean_primary_6nodes.v#, labels_soybean_primary_6nodes.v#
- `<ROOT>/20250102_generalizability_experiment/primary/younger_rice` holds 2 families: labels_rice_primary_6nodes.v#, labels_rice_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment/arabidopsis` holds 3 families: labels_ONLYarabidopsis_primary_6nodes.v#, labels_canola_pennycress_arabidopsis.v#, labels_canola_pennycress_arabidopsis.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment/canola` holds 4 families: labels_ONLYcanola_primary_6nodes.v#, labels_canola_pennycress_primary_6nodes.v#, labels_canola_primary_6nodes.v#, labels_canola_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment/sorghum` holds 2 families: labels_sorghum_5-12DAG_primary_6nodes.v#, labels_sorghum_5-12DAG_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment/soybean` holds 2 families: labels_soybean_primary_6nodes.v#, labels_soybean_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment/younger_rice` holds 2 families: labels_rice_primary_6nodes.v#, labels_rice_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment_SETUP/arabidopsis` holds 3 families: labels_ONLYarabidopsis_primary_6nodes.v#, labels_canola_pennycress_arabidopsis.v#, labels_canola_pennycress_arabidopsis.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment_SETUP/canola` holds 4 families: labels_ONLYcanola_primary_6nodes.v#, labels_canola_pennycress_primary_6nodes.v#, labels_canola_primary_6nodes.v#, labels_canola_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment_SETUP/sorghum` holds 2 families: labels_sorghum_5-12DAG_primary_6nodes.v#, labels_sorghum_5-12DAG_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment_SETUP/soybean` holds 2 families: labels_soybean_primary_6nodes.v#, labels_soybean_primary_6nodes.v#
- `<ROOT>/20250415_primary_root_generalizability_experiment_SETUP/younger_rice` holds 2 families: labels_rice_primary_6nodes.v#, labels_rice_primary_6nodes.v#
- `<ROOT>/SLEAP_Canola_Pennycress/lateral_3_nodes` holds 9 families: 13do_canola_lateral_labels_angel.v#, 13do_canola_lateral_labels_hannah.v#, 13do_lr_labels_hannah_v001, Canola_LateralRoot (1).v#, Canola_LateralRoot.v#, LR_13DO_KE, hc_lr_labels.v#, labels_canola_lateral_3nodes.v#, and 1 more
- `<ROOT>/SLEAP_Canola_Pennycress/lateral_3_nodes/h5_files_for_LR_sleap_project/13_do/h5_files_13do/hannah` holds 2 families: 13do_lr_labels_hannah_v001, 13do_pr_labels_hannah_v001
- `<ROOT>/SLEAP_Canola_Pennycress/primary_root` holds 11 families: 13do_pr_labels_hannah_v001, 2_DO_PR_labels_KE.v#, AAP_primary_root_labels.v#, Canola_PrimaryRoot, Canola_PrimaryRoot_V2, canola_pr_old_6_nodes_labels (1).v#, canola_pr_old_6_nodes_labels.v#, canola_pr_old_6_nodes_labels.v#, and 3 more
- `<ROOT>/SLEAP_Canola_Pennycress/primary_root/h5_files_for_PR_sleap_project/13_do/hannah` holds 2 families: 13do_lr_labels_hannah_v001, 13do_pr_labels_hannah_v001
- `<ROOT>/SLEAP_Rice/10_and_3_do_merge` holds 3 families: labels_10do_copy.v#, labels_3_do_2021_22.v#_copy, labels_3do_10do_merge.v#
- `<ROOT>/SLEAP_Rice/10_do/main_root` holds 6 families: labels.v#, labels_10_do.v#, labels_10do_6nodes.v#, labels_10do_6nodes.v#, labels_rice_10do_6nodes.v#, labels_rice_10do_6nodes.v#
- `<ROOT>/SLEAP_Rice/10_do/main_root/FN2021` holds 3 families: FN2021_20frames.v#, labels.v#, labels_10_do.v#
- `<ROOT>/SLEAP_Rice/3_do/3_Days_Old_longest_root` holds 5 families: labels.v#, labels_rice_3dag_primary_6nodes.v#, labels_rice_3dag_primary_6nodes.v#, labels_rice_3do_primary_6nodes.v#, rice_3do_longest_labels.v#
- `<ROOT>/SLEAP_Rice/3_do/main_root` holds 5 families: labels_3_do.v#, labels_3_do_2021_22.v#, labels_rice_3do_main_6nodes.v#, labels_rice_3do_main_6nodes.v#, labels_rice_main_6nodes.v#
- `<ROOT>/SLEAP_Rice/5do_lateral_2nodes_hydroponic` holds 2 families: labels_2nodes.v#, labels_2nodes_remove_11do.v#
- `<ROOT>/SLEAP_Rice/Hydroponic/5DAG_lateral/3_nodes` holds 3 families: labels.v#, labels.v#_CV, labels.v#_JM
- `<ROOT>/SLEAP_Rice/Hydroponic/5DAG_primary` holds 4 families: 5DAG_primary_hydroponic_rice_labels.v#, labels_AAP.v#, labels_JT.v#, labels_rice_3dag_primary_6nodes.v#
- `<ROOT>/SLEAP_Rice/Hydroponic/5DAG_seminal_plus_primary` holds 3 families: 5DAG_main_hydroponic_labels.v#, labels_3_do_2021_22.v#, labels_Hoagland_AAP.v#
- `<ROOT>/SLEAP_Rice/primary_3-5do` holds 2 families: labels_rice_primary_6nodes.v#, labels_rice_primary_6nodes.v#
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/lateral/both-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/lateral/brightness-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/lateral/contrast-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/lateral/none-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/primary/both-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/primary/brightness-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/primary/contrast-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/2026-05-01_aug_retrain/primary/none-seed0` holds 3 families: test, train, val
- `<ROOT>/SLEAP_Soy/lateral_root_4_nodes` holds 4 families: javiers_lateral_labels.v#, labels_soy_lateral_4nodes.v#, labels_soy_lateral_4nodes.v#, older_soy_lr_merged.v#
- `<ROOT>/SLEAP_arabidopsis` holds 2 families: merged, merged.01
- `<ROOT>/SLEAP_arabidopsis/lateral_root/3_nodes` holds 3 families: Canola_LateralRoot.v#, labels.v#, labels_canola_pennycress_arabidopsis.v#
- `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7-14_do` holds 8 families: javiers_labels.v#_4 nodes merged, javiers_labels.v#_4 nodes merged copy, javiers_labels.v#_4 nodes_11222023, javiers_lateral_labels_4nodes.v#, javiers_lateral_labels_4nodes.v005 - Copy, label_laterals14DAP_.v#, labels_arabidopsis_lateral_4nodes.v#, labels_arabidopsis_lateral_4nodes.v#
- `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7_do` holds 7 families: EM_labels.v#, labels.v#, labels.v#_HC, labels_7DAP_laterals_KE, labels_7DAP_laterals_MK.v#, labels_arabidopsis_lateral_4nodes.v#, labels_arabidopsis_lateral_4nodes.v#
- `<ROOT>/SLEAP_arabidopsis/lateral_root/4_nodes/7_do/old_labels_juan_gonzalez` holds 2 families: labels_7DAP_laterals_.v#, labels_7DAP_laterals_ONLY.v#
- `<ROOT>/SLEAP_arabidopsis/lateral_root/7_do` holds 2 families: labels_7DAP_laterals_.v#, labels_7DAP_laterals_ONLY.v#
- `<ROOT>/SLEAP_arabidopsis/primary_root/primary_6nodes` holds 15 families: 13do_pr_labels_hannah_v001, 2_DO_PR_labels_KE.v#, AAP_primary_root_labels.v#, canola_pr_old_6_nodes_labels.v#, javiers_labels.v#_6 nodes merged, javiers_labels.v#_6 nodes merged copy, javiers_labels.v#_6 nodes_11222023, javiers_labels_6nodes.v#, and 7 more
- `<ROOT>/SLEAP_arabidopsis_plates/7_dap/labels` holds 7 families: IAAlabels.v#, IAAlabels.v#, IAAlabels.v#_predictions_only, labels.v#, labels.v#_labels, labels.v#_labels_copy, labels.v#_preds
- `<ROOT>/SLEAP_arabidopsis_plates/IAA_treated_7DAP/labels` holds 5 families: 7_20230324-091436_001.primary_7dap.predictions_copy, IAAlabels.v#, IAAlabels.v#, IAAlabels.v#_predictions_only, labels_v008
- `<ROOT>/SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/lateral_roots/labels` holds 2 families: labels.v#, lateral_labels.v#
- `<ROOT>/SLEAP_arabidopsis_plates/PLATE_arabidopsis/PLATE_arabidopsis/primary_root/labels` holds 4 families: day2and3 copy, labels.v#, labels_wheat_2-3DAG, labels_wheat_2-3DAG.v#
- `<ROOT>/SLEAP_arabidopsis_plates/SLEAP_models_arabidopsis_plates_20250708/SLEAP_models_arabidopsis_plates/Arabidopsis_plates/0908-0901_plates` holds 2 families: lateral_labels.v#, primary_labels.v#
- `<ROOT>/SLEAP_arabidopsis_plates/SLEAP_models_arabidopsis_plates_20250708/SLEAP_models_arabidopsis_plates/primary_root_8nodes/7_dap/labels` holds 7 families: IAAlabels.v#, IAAlabels.v#, IAAlabels.v#_predictions_only, labels.v#, labels.v#_labels, labels.v#_labels_copy, labels.v#_preds
- `<ROOT>/SLEAP_arabidopsis_plates/SLEAP_models_arabidopsis_plates_20250708/SLEAP_models_arabidopsis_plates/tif_files/IAA_Day7` holds 4 families: IAALabelsv007, IAALabelsv008, IAAlabels.v#_predictions_only, IAAlabels.v#_predictions_only
- `<ROOT>/SLEAP_arabidopsis_plates/SLEAP_models_arabidopsis_plates_20250708/SLEAP_models_arabidopsis_plates/tif_files/IAA_treated_7DAP/labels` holds 5 families: 7_20230324-091436_001.primary_7dap.predictions_copy, IAAlabels.v#, IAAlabels.v#, IAAlabels.v#_predictions_only, labels_v008
- `<ROOT>/SLEAP_arabidopsis_plates/labels/lateral_3nodes` holds 3 families: labels.v#, lateral_labels.uncropped.v#, lateral_labels.v#
- `<ROOT>/SLEAP_arabidopsis_plates/labels/primary_8nodes` holds 3 families: labels.v#, labels_wheat_2-3DAG, labels_wheat_2-3DAG.v#
- `<ROOT>/SLEAP_arabidopsis_plates/old_labels` holds 3 families: IAAlabels.v#, IAAlabels.v#, IAAlabels.v#_predictions_only
- `<ROOT>/SLEAP_circumnutation/labels` holds 14 families: exp1-sd1-sd1_plate001_labels_bihourly, exp1-sd1-sd1_plate002_labels_bihourly, exp1-sd1-sd1_plate003_labels_bihourly, exp1-sd1-sd1_plate004_labels_bihourly, exp2-sd1-tzt_plate001_labels_bihourly, exp2-sd1-tzt_plate002_labels_bihourly, rice-test_plate001_labels_hourly, rice-test_plate002_labels_hourly, and 6 more
- `<ROOT>/SLEAP_circumnutation/rice-test/004` holds 2 families: plate_004.labels, plate_004_test_copy.labels
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/exp1-sd1-sd1/labels` holds 4 families: plate001_labels_bihourly, plate002_labels_bihourly, plate003_labels_bihourly, plate004_labels_bihourly
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/exp2-sd1-tzt/labels` holds 2 families: plate001_labels_bihourly, plate002_labels_bihourly
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/rice-test/h5_videos` holds 2 families: all_plate_videos_color.v#, all_plate_videos_greyscale.v#
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/rice-test/labels` holds 4 families: plate001_labels_hourly, plate002_labels_hourly, plate004_labels_hourly, plate_labels_hourly_combined
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/scanning-room/h5_videos` holds 2 families: plate_videos_color, plate_videos_greyscale
- `<ROOT>/SLEAP_circumnutation/suyashs_exps_20250819/scanning-room/labels` holds 3 families: plate001_labels_hourly, plate002_labels_hourly, plate003_labels_hourly
- `<ROOT>/SLEAP_covercress_plates/lateral` holds 2 families: labels_lateral_2025-06-20_T3_day_11.v#, labels_laterals_covercress_13DO_3nodes.v#
- `<ROOT>/SLEAP_medicago/Downstream_Data_Analysis/Downstream_Data_Analysis` holds 9 families: AAP_D12_pr_labels.v#, AAP_D14_lr_labels.v#, AAP_D14_pr_labels.v#, AAP_D8_pr_labels.v#, EM_D12_lr_labels.v#, JT_D4_pr_labels.v#, JT_D8_lr_labels.v#, KE_D21_lr_labels.v#, and 1 more
- `<ROOT>/SLEAP_medicago/lateral_root` holds 7 families: AAP_D14_lr_labels.v#, EM_D12_lr_labels.v#, JT_D8_lr_labels.v#, KE_D21_lr_labels.v#, canola_pennycress_medicago_lateral_root_labels.v#, labels_canola_lateral_3nodes.v#, medicago_lateral_root_labels.v#
- `<ROOT>/SLEAP_medicago/primary_root` holds 7 families: AAP_D12_pr_labels.v#, AAP_D14_pr_labels.v#, AAP_D8_pr_labels.v#, JT_D4_pr_labels.v#, KE_D21_pr_labels.v#, labels_canola_pennycress_arabidopsis.v#, medicago_primary_root_labels.v#
- `<ROOT>/SLEAP_medicago_plates/combined_roots` holds 9 families: MK22_lateral_combined, MK22_primary_combined, MK22_tertiary_combined, MK24_lateral_combined, MK24_primary_combined, MK24_tertiary_combined, MK31_lateral_combined, MK31_primary_combined, and 1 more
- `<ROOT>/SLEAP_medicago_plates/lateral` holds 6 families: lateral_root_MK22_Day14_labels.v#, lateral_root_MK22_Day14_labels_deleted_predicted_instances.v#, lateral_root_MK22_Day14_labels_for_model_building.v#, lateral_root_MK22_Day14_labels_for_model_building.v#, lateral_root_MK22_Day14_labels_for_model_building.v#_updated_paths, lateral_root_MK31_Day5_labels.v#
- `<ROOT>/SLEAP_medicago_plates/lateral/scratch` holds 2 families: lateral_root_MK22_Day14_labels_for_model_building.v#, lateral_root_MK22_Day14_labels_for_model_building.v#_replaced_filenames
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/datasets` holds 2 families: minimal_instance, small_robot_minimal
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_bottomup` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_centered_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_centroid` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_multiclass_bottomup` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_multiclass_centered_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/minimal_instance_single_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/lateral/sleap-nn/tests/assets/model_ckpts/single_instance_with_metrics` holds 5 families: labels_train_gt_0, labels_val_gt_0, pred_test, pred_train_0, pred_val_0
- `<ROOT>/SLEAP_medicago_plates/primary` holds 3 families: primary_root_MK22_Day10_labels.v#, primary_root_MK22_Day14_labels.v#, primary_root_MK22_Day14_labels.v#
- `<ROOT>/SLEAP_medicago_plates/tertiary` holds 3 families: tertiary_root_MK22_Day14_labels.v#, tertiary_root_MK22_Day14_labels.v#, tertiary_root_MK22_Day14_labels.v#_updated_filenames
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/datasets` holds 2 families: minimal_instance, small_robot_minimal
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_bottomup` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_centered_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_centroid` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_multiclass_bottomup` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_multiclass_centered_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/minimal_instance_single_instance` holds 2 families: labels_train_gt_0, labels_val_gt_0
- `<ROOT>/SLEAP_medicago_plates/tertiary/sleap-nn/tests/assets/model_ckpts/single_instance_with_metrics` holds 5 families: labels_train_gt_0, labels_val_gt_0, pred_test, pred_train_0, pred_val_0
- `<ROOT>/SLEAP_multiple_species/primary_roots_6_nodes` holds 4 families: canola_pr_old_6_nodes_labels.v#, labels_arabidopsis_primary.v#, rice_3do_longest_labels.v#, soy_labels_pr_678do.v#
- `<ROOT>/SLEAP_packages_10-24-23` holds 9 families: labels_arabidopsis_lateral_4nodes.v#, labels_arabidopsis_primary.v#, labels_canola_lateral_3nodes.v#, labels_canola_primary_6nodes.v#, labels_rice_10do_6nodes.v#, labels_rice_3dag_primary_6nodes.v#, labels_rice_3do_main_6nodes.v#, labels_soy_lateral_4nodes.v#, and 1 more
- `<ROOT>/SLEAP_shoots` holds 2 families: updatedsmall, updatedsmall copy
- `<ROOT>/SLEAP_sorghum/lateral_4nodes` holds 7 families: 10do_lateral_labels_AAP.v#, 5do_lateral_labels_HC.v#, labels(fast 6 Lateral).v#, labels_soy_lateral_4nodes.v#, labels_soybean_sorghum_lateral_roots_4nodes.v#, sorghum_lateral_roots_4nodes_labels.v#, sorghum_lateral_roots_4nodes_labels.v#
- `<ROOT>/SLEAP_sorghum/primary_6nodes` holds 18 families: KatePrimaryDay12 (1), KatePrimaryDay30Practice, labels.v#, labels.v#_kate, labels.v001 (Fast D6 Primary labeled), labels.v001xt, labels.v004xt, labels_D10_KE.v#, and 10 more
- `<ROOT>/SLEAP_sorghum/seminal_root_6nodes` holds 2 families: 10do_seminal_labels_HC.v#, 5do_seminal_labels_AAP.v#
- `<ROOT>/SLEAP_wheat/lateral` holds 6 families: labels_lateral_11DAG.v#, labels_lr_D11_AAP.v#, labels_lr_D11_AAP2.v#, labels_lr_D11_EM.v#, labels_lr_D11_JT.v#, labels_lr_D11_KE.v#
- `<ROOT>/SLEAP_wheat/primary` holds 4 families: labels_pr_D5_KE.v#, labels_primary_wheat_5DAG_rice_3DAG.v#, labels_rice_3dag_primary_6nodes.v#, labels_wheat_primary_5DAG.v#
- `<ROOT>/SLEAP_wheat/seminal` holds 7 families: labels_rice_10do_6nodes.v#, labels_rice_3do_main_6nodes.v#, labels_seminal_wheat_5-14DAG_rice_3-10DAG.v#, labels_sr_5-14DAG.v#, labels_sr_D11_AAP.v#, labels_sr_D14_AAP.v#, labels_sr_D5_KE.v#
- `<ROOT>/experiments/output` holds 3 families: sorghum-primary-2025-01-06_v000_test_labels, sorghum-primary-2025-01-06_v001_test_labels, sorghum-primary-2025-01-06_v002_test_labels
- `<ROOT>/fixing_arabidopsis_plates` holds 4 families: labels_plates_arabidopsis_primary_2-7DAP_8nodes.uncropped.v#, labels_plates_arabidopsis_primary_2-7DAP_8nodes.v#, lateral_labels.uncropped.v#, lateral_labels.v#
- `<ROOT>/generalizability_exp_01142023/primary_root/soybean_primary` holds 2 families: labels_soybean_primary_6nodes.v#, labels_soybean_primary_6nodes.v#
- `<ROOT>/latest_labels_and_images/PLATE_arabidopsis/primary` holds 2 families: labels_plates_arabidopsis_primary_2-7DAP_8nodes.uncropped.v#, labels_plates_arabidopsis_primary_2-7DAP_8nodes.v#
- `<ROOT>/primary` holds 2 families: primary_root_MK22_Day10_labels.v#, primary_root_MK22_Day14_labels.v#

## How to read this

`species`, `mode` and `root_type` are **name-derived**: read off the path, not
out of the file. They are *not evidence* of what a file contains. Node counts,
frame counts and instance counts are read from the files themselves and are.

Referenced video paths are emitted as filenames alone, and any candidate that
could not be expressed relative to the root is reported by filename only.
