# Data Dictionary

Source analyzed: `Bisoprolol_icsr_sample_1068rows.xlsx`, single worksheet. The challenge documentation names a CSV; this workbook is the supplied dataset and was not modified.

`case-level` means one value is expected per `safetyreportid`; repeated IDs must be reconciled before case-level analysis. `reaction-level` denotes fields that describe a reaction. Drug-level fields may contain comma-delimited values and are not assumed to align one-to-one with reactions without further validation.

| Column name | Meaning | Data type | Missing | Example value | Used in analysis | Level |
|---|---|---|---:|---|---|---|
| `safetyreportversion` | Version number of the safety report. | `int64` | 0 (0.00%) | 1 | No | case-level |
| `safetyreportid` | Safety report identifier; used as the case identifier. | `int64` | 0 (0.00%) | 24780403 | Yes | case-level |
| `primarysourcecountry` | Country supplied for the primary source. | `str` | 0 (0.00%) | italy | No | case-level |
| `occurcountry` | Country where the event/case occurred. | `str` | 7 (0.66%) | italy | Yes | case-level |
| `transmissiondateformat` | Format code associated with transmissiondate. | `int64` | 0 (0.00%) | 102 | No | case-level |
| `transmissiondate` | Transmission date as supplied in the source extract. | `int64` | 0 (0.00%) | 20250115 | No | case-level |
| `reporttype` | Reported case/report type. | `str` | 0 (0.00%) | spontaneous report | Yes | case-level |
| `serious` | Overall serious/non-serious classification. | `str` | 0 (0.00%) | serious | Yes | case-level |
| `seriousnessdeath` | Seriousness criterion: death. | `str` | 0 (0.00%) | no | Yes | case-level |
| `seriousnesslifethreatening` | Seriousness criterion: life-threatening event. | `str` | 0 (0.00%) | no | Yes | case-level |
| `seriousnesshospitalization` | Seriousness criterion: hospitalization or prolongation of hospitalization. | `str` | 0 (0.00%) | yes | Yes | case-level |
| `seriousnessdisabling` | Seriousness criterion: persistent/significant disability or incapacity. | `str` | 0 (0.00%) | no | Yes | case-level |
| `seriousnesscongenitalanomali` | Seriousness criterion: congenital anomaly/birth defect (source field spelling retained). | `str` | 0 (0.00%) | no | Yes | case-level |
| `seriousnessother` | Seriousness criterion: other medically important condition. | `str` | 0 (0.00%) | yes | Yes | case-level |
| `receivedateformat` | Format code associated with receivedate. | `int64` | 0 (0.00%) | 102 | No | case-level |
| `receivedate` | Date the case was received; used to determine the reporting period. | `int64` | 0 (0.00%) | 20241227 | Yes | case-level |
| `receiptdateformat` | Format code associated with receiptdate. | `int64` | 0 (0.00%) | 102 | No | case-level |
| `receiptdate` | Receipt date as supplied in the source extract. | `int64` | 0 (0.00%) | 20241227 | No | case-level |
| `fulfillexpeditecriteria` | Flag indicating whether the case fulfills expedited-reporting criteria; used as 15-day Alert proxy. | `str` | 0 (0.00%) | yes | Yes | case-level |
| `companynumb` | Company case number as supplied in the source extract. | `str` | 1 (0.09%) | IT-MINISAL02-1015898 | No | case-level |
| `primarysource_reportercountry` | Country of the primary reporter. | `str` | 0 (0.00%) | italy | Yes | case-level |
| `primarysource_qualification` | Primary reporter qualification. | `str` | 0 (0.00%) | pharmacist | Yes | case-level |
| `sender_sendertype` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | pharmaceutical company | No | case-level |
| `sender_senderorganization` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | AUROBINDO | No | case-level |
| `receiver_receivertype` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | other | No | case-level |
| `receiver_receiverorganization` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | FDA | No | case-level |
| `patient_patientonsetage` | Patient age at onset, with unit in patient_patientonsetageunit. | `float64` | 91 (8.52%) | 85.0 | Yes | case-level |
| `patient_patientonsetageunit` | Unit for patient age at onset. | `object` | 81 (7.58%) | year | Yes | case-level |
| `patient_patientsex` | Patient sex. | `str` | 30 (2.81%) | female | Yes | case-level |
| `patient_reaction_reactionmeddraversionpt` | MedDRA version(s) associated with the reported Preferred Term(s). | `object` | 0 (0.00%) | 27.1,27.1 | No | reaction-level |
| `patient_reaction_reactionmeddrapt` | Reported reaction coded as MedDRA Preferred Term(s); used for reaction analysis. | `str` | 0 (0.00%) | Rectal haemorrhage,Deficiency anaemia | Yes | reaction-level |
| `patient_reaction_reactionoutcome` | Outcome(s) for reported reaction(s). | `str` | 0 (0.00%) | unknown,unknown | Yes | reaction-level |
| `patient_drug_drugcharacterization` | Drug role/characterization value(s) as supplied (for example, suspect or concomitant). | `str` | 0 (0.00%) | suspect,concomitant,concomitant,concomitant,concomitant,concomitant,concomitant,concomitant,concomitant,concomitant,conc | No | drug-level / delimited multi-value field |
| `patient_drug_medicinalproduct` | Medicinal product name(s) as supplied. | `str` | 0 (0.00%) | CLOPIDOGREL BISULFATE,PANTOPRAZOLE SODIUM,PREDNISONE,SODIUM BICARBONATE,BISOPROLOL FUMARATE,DIAMOX SEQUELS,LASIX,NITROGL | Yes | drug-level / delimited multi-value field |
| `patient_drug_drugauthorizationnumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 4 (0.37%) | 90540 | No | drug-level / delimited multi-value field |
| `patient_drug_drugstructuredosagenumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 153 (14.33%) | 75,20,5,500,2.5,250,500,15,300,50 | No | drug-level / delimited multi-value field |
| `patient_drug_drugstructuredosageunit` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 153 (14.33%) | mg,mg,mg,mg,mg,mg,mg,mg,mg,mg | No | drug-level / delimited multi-value field |
| `patient_drug_drugseparatedosagenumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 290 (27.15%) | 1,1,1,1,2,2,1,1,1 | No | drug-level / delimited multi-value field |
| `patient_drug_drugintervaldosageunitnumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 330 (30.90%) | 1,1,1,1,1,1,1,1,1 | No | drug-level / delimited multi-value field |
| `patient_drug_drugintervaldosagedefinition` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 330 (30.90%) | month,month,month,month,month,month,month,month,month | No | drug-level / delimited multi-value field |
| `patient_drug_drugdosagetext` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 244 (22.85%) | 75 MILLIGRAM, ONCE A DAY (IN THE MORNING),20 MILLIGRAM, ONCE A DAY (IN THE MORNING),5 MILLIGRAM, ONCE A DAY (IN THE MORN | No | drug-level / delimited multi-value field |
| `patient_drug_drugdosageform` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 378 (35.39%) | Film-coated tablet,Tablet,Tablet,Tablet,Tablet,Tablet,Tablet,Transdermal system,Tablet,Tablet,Tablet,Tablet,Tablet | No | drug-level / delimited multi-value field |
| `patient_drug_drugadministrationroute` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 23 (2.15%) | oral,oral,oral,oral,oral,oral,oral,transmammary,oral,oral,oral,oral,oral | No | drug-level / delimited multi-value field |
| `patient_drug_drugindication` | Indication(s) for the listed drug product(s). | `str` | 0 (0.00%) | Arterial thrombosis,Gastrooesophageal reflux disease,Gouty arthritis,Hyperchlorhydria,Hypertension,Epilepsy,Renal failur | Yes | drug-level / delimited multi-value field |
| `patient_drug_actiondrug` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown,unknown | No | drug-level / delimited multi-value field |
| `patient_drug_drugadditional` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 21 (1.97%) | placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo,placebo | No | drug-level / delimited multi-value field |
| `patient_drug_activesubstance_activesubstancename` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 0 (0.00%) | CLOPIDOGREL BISULFATE,PANTOPRAZOLE SODIUM,PREDNISONE,SODIUM BICARBONATE,BISOPROLOL FUMARATE,ACETAZOLAMIDE,FUROSEMIDE,NIT | No | drug-level / delimited multi-value field |
| `patient_summary_narrativeincludeclinical` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 355 (33.24%) | CASE EVENT DATE: 20241130 | No | case-level |
| `drugs` | Drug names/active substances as supplied in the extract. | `str` | 0 (0.00%) | ALLOPURINOL,BISOPROLOL FUMARATE,CLOPIDOGREL BISULFATE,DIAMOX SEQUELS,LASIX,Luvion,NITROGLYCERIN,PANTOPRAZOLE SODIUM,PHEN | No | drug-level / delimited multi-value field |
| `report_date` | Report date field included in the source extract. | `datetime64[us]` | 0 (0.00%) | 2024-12-27 | No | case-level |
| `patient_patientweight` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `float64` | 579 (54.21%) | 62.0 | No | case-level |
| `patient_drug_drugstartdateformat` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 417 (39.04%) | 102102102102 | No | drug-level / delimited multi-value field |
| `patient_drug_drugstartdate` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 417 (39.04%) | 20240711,20240711,20240711,20240711 | No | drug-level / delimited multi-value field |
| `patient_drug_drugenddateformat` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 532 (49.81%) | 102102102102 | No | drug-level / delimited multi-value field |
| `patient_drug_drugenddate` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 532 (49.81%) | 20240711,20240711,20240711,20240711 | No | drug-level / delimited multi-value field |
| `patient_drug_drugtreatmentduration` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 622 (58.24%) | 1,1,1,1 | No | drug-level / delimited multi-value field |
| `patient_drug_drugtreatmentdurationunit` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 622 (58.24%) | day,day,day,day | No | drug-level / delimited multi-value field |
| `patient_drug_drugcumulativedosagenumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 880 (82.40%) | 63,3000,3000,3000,17.591,5,5 | No | drug-level / delimited multi-value field |
| `patient_drug_drugcumulativedosageunit` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 880 (82.40%) | 002,003,003,003,002,032,032 | No | drug-level / delimited multi-value field |
| `primarysource_literaturereference` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 911 (85.30%) | Villarejo-Elena C, Pacheco-Yepes MR, P?rez-Belmonte LM, G?mez-Huelgas R... Tratamiento con urea oral en paciente con ins | No | case-level |
| `duplicate` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `float64` | 850 (79.59%) | 1.0 | No | case-level |
| `reportduplicate_duplicatesource` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 890 (83.33%) | RDY | No | case-level |
| `reportduplicate_duplicatenumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 850 (79.59%) | DE-RDY-DEU/2025/02/002080 | No | case-level |
| `patient_drug_drugrecurreadministration` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `str` | 971 (90.92%) | yes_unknown,yes_unknown | No | drug-level / delimited multi-value field |
| `patient_drug_drugbatchnumb` | Not established by the supplied documentation; retained as a source field (see field name and example value). | `object` | 1021 (95.60%) | UNK | No | drug-level / delimited multi-value field |
| `patient_patientagegroup` | Coarse patient age-group field supplied in the extract. | `str` | 1037 (97.10%) | elderly | Yes | case-level |
| `authoritynumb` | Authority number as supplied in the source extract. | `str` | 1067 (99.91%) | GB-MHRA-MIDB-3eade4aa-0be1-440f-9a24-47ba272e181a | No | case-level |
