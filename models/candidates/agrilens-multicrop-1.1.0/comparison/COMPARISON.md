# Model comparison: 1.0.0 vs 1.1.0 (application six-view path, each model with its own gates)

Gates: 1.0.0 {'confidence': 0.4, 'margin': 0.12, 'ood_logit': 2.1}; 1.1.0 {'confidence': 0.4, 'margin': 0.12, 'ood_logit': 2.9}.

| Set | n | Metric | 1.0.0 | 1.1.0 | Change |
|---|---|---|---|---|---|
| val | 3844 | top1_accuracy | 0.9683 | 0.9758 | +0.0075 |
| val | 3844 | macro_f1 | 0.9656 | 0.9737 | +0.0082 |
| val | 3844 | correct_and_accepted | 0.9631 | 0.9654 | +0.0023 |
| val | 3844 | rejected_unknown | 0.0081 | 0.0146 | +0.0065 |
| val | 3844 | wrong_but_accepted | 0.0286 | 0.0200 | -0.0086 |
| val_c270_proxy | 3844 | top1_accuracy | 0.8577 | 0.9644 | +0.1067 |
| val_c270_proxy | 3844 | macro_f1 | 0.8693 | 0.9571 | +0.0878 |
| val_c270_proxy | 3844 | correct_and_accepted | 0.8130 | 0.9511 | +0.1381 |
| val_c270_proxy | 3844 | rejected_unknown | 0.0963 | 0.0213 | -0.0749 |
| val_c270_proxy | 3844 | wrong_but_accepted | 0.0892 | 0.0276 | -0.0617 |
| test_known_device | 3595 | top1_accuracy | 0.9586 | 0.9744 | +0.0159 |
| test_known_device | 3595 | macro_f1 | 0.9270 | 0.9610 | +0.0340 |
| test_known_device | 3595 | correct_and_accepted | 0.9519 | 0.9661 | +0.0142 |
| test_known_device | 3595 | rejected_unknown | 0.0159 | 0.0153 | -0.0006 |
| test_known_device | 3595 | wrong_but_accepted | 0.0323 | 0.0186 | -0.0136 |
| test_heldout_device | 325 | top1_accuracy | 0.8677 | 0.9692 | +0.1015 |
| test_heldout_device | 325 | macro_f1 | 0.6142 | 0.7588 | +0.1445 |
| test_heldout_device | 325 | correct_and_accepted | 0.8215 | 0.8985 | +0.0769 |
| test_heldout_device | 325 | rejected_unknown | 0.0585 | 0.0831 | +0.0246 |
| test_heldout_device | 325 | wrong_but_accepted | 0.1200 | 0.0185 | -0.1015 |
| ood_eval | 245 | accepted_rate | 0.3551 | 0.3347 | -0.0204 |
| ood_eval | 245 | unknown_rate | 0.6449 | 0.6653 | +0.0204 |

Mango per-class recall (test_known_device):

| Class | 1.0.0 | 1.1.0 |
|---|---|---|
| Mango_Anthracnose | 0.959 | 1.000 |
| Mango_Bacterial_Canker | 1.000 | 1.000 |
| Mango_Cutting_Weevil | 1.000 | 1.000 |
| Mango_Die_Back | 0.462 | 0.904 |
| Mango_Gall_Midge | 1.000 | 1.000 |
| Mango_Healthy | 0.920 | 0.825 |
| Mango_Powdery_Mildew | 0.959 | 0.964 |
| Mango_Sooty_Mould | 1.000 | 0.978 |

`val` was used for selection and calibration; `val_c270_proxy` is simulated and related to the candidate's training augmentation; only real Logitech C270 captures on the kiosk can confirm live behaviour. For ood_eval, lower accepted_rate is better.
