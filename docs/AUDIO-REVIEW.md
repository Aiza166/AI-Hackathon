# Sindhi and Punjabi audio review

Clips are pre-generated with ElevenLabs `eleven_v3` from the machine-assisted text packs (`frontend/src/i18n/sd.ts`, `pa.ts`). No native speaker has reviewed them yet. Listen to each clip (open the path under `frontend/public/audio/<lang>/`) and mark the last column OK or bad. Regenerate a bad clip by fixing its pack text, deleting the mp3 and running `python backend/scripts/generate_local_audio.py`.

Keys with no pack text keep the Urdu voice: prompt_home, prompt_welcome, prompt_document_photos, prompt_safeswitch, prompt_scam_intro, mydata_*, outbox_*, and the status_saved fallback.

## Sindhi

| audioKey | Text | Clip | Size | OK / bad |
|---|---|---|---|---|
| prompt_account | پينشن ڪهڙي بئنڪ کاتي ۾ اچي؟ | audio/sd/prompt_account.mp3 | 8.3 KB | |
| prompt_deceased | مرحوم جو پورو نالو ڇا هو؟ | audio/sd/prompt_deceased.mp3 | 9.2 KB | |
| prompt_deceased_cnic | مرحوم جي شناختي ڪارڊ جو نمبر (جيڪڏهن ڄاڻو ٿا) | audio/sd/prompt_deceased_cnic.mp3 | 13.0 KB | |
| prompt_dob | توهان جي ڄمڻ جي تاريخ ڪهڙي آهي؟ | audio/sd/prompt_dob.mp3 | 10.4 KB | |
| prompt_documents | توهان وٽ ڪهڙا ڪاغذ آهن؟ | audio/sd/prompt_documents.mp3 | 8.3 KB | |
| prompt_relation | توهان مرحوم جا ڇا لڳو ٿا؟ | audio/sd/prompt_relation.mp3 | 7.1 KB | |
| prompt_review | دعويٰ موڪلڻ کان اڳ سڀ ڪجهه ڏسي وٺو | audio/sd/prompt_review.mp3 | 10.8 KB | |
| reason_account_not_owned | هي بئنڪ کاتو توهان جي نالي تي ناهي. مهرباني ڪري پنهنجي نالي وارو کاتو ڏيو. | audio/sd/reason_account_not_owned.mp3 | 24.5 KB | |
| reason_account_reused | هي کاتو ٻين دعوائن ۾ به استعمال ٿيو آهي. هڪ آفيسر جانچ ڪندو. | audio/sd/reason_account_reused.mp3 | 18.6 KB | |
| reason_already_drawing | رڪارڊ موجب توهان اڳ ۾ ئي هڪ خانداني پينشن وٺي رهيا آهيو. هڪ آفيسر جانچ ڪندو. | audio/sd/reason_already_drawing.mp3 | 25.1 KB | |
| reason_approved | توهان جي دعويٰ منظور ٿي وئي آهي. پهرين ادائيگي جلد توهان جي کاتي ۾ پهچي ويندي. | audio/sd/reason_approved.mp3 | 26.1 KB | |
| reason_child_over_age | قاعدن موجب هن عمر جي پٽ جي دعويٰ جو جائزو هڪ آفيسر وٺندو. | audio/sd/reason_child_over_age.mp3 | 18.9 KB | |
| reason_confirm_dob | مهرباني ڪري پنهنجي ڄمڻ جي تاريخ جي تصديق ڪريو. اها توهان جي شناختي ڪارڊ تي لکيل آهي. | audio/sd/reason_confirm_dob.mp3 | 25.8 KB | |
| reason_daughter_married | قاعدن موجب هڪ آفيسر ڌيءُ جي دعويٰ جو جائزو وٺندو. | audio/sd/reason_daughter_married.mp3 | 14.8 KB | |
| reason_death_not_verified | وفات جي رڪارڊ جي اڃا تصديق نه ٿي سگهي. هڪ آفيسر جانچ ڪندو. | audio/sd/reason_death_not_verified.mp3 | 19.5 KB | |
| reason_dob_mismatch | توهان جي ٻڌايل ڄمڻ جي تاريخ رڪارڊ سان نٿي ملي. پنهنجي شناختي ڪارڊ مان ڏسي ٻيهر ٻڌايو، يا مددگار کي ڪارڊ ڏيکاريو. | audio/sd/reason_dob_mismatch.mp3 | 35.1 KB | |
| reason_doc_edit_risk | توهان جي ڪاغذ جي وڌيڪ جانچ ضروري آهي. هڪ آفيسر ان کي ڏسندو. | audio/sd/reason_doc_edit_risk.mp3 | 20.8 KB | |
| reason_doc_mismatch | توهان جي ڪاغذ جون ڪجهه معلومات سرڪاري رڪارڊ سان نٿيون ملن. مهرباني ڪري هن ڪاغذ جي صاف تصوير يا ٻي ڪاپي موڪليو. | audio/sd/reason_doc_mismatch.mp3 | 37.7 KB | |
| reason_duplicate_claim | هن پينشن لاءِ ڪنهن ٻئي به دعويٰ ڪئي آهي. هڪ آفيسر ٽن ڏينهن ۾ جانچ ڪندو. | audio/sd/reason_duplicate_claim.mp3 | 23.6 KB | |
| reason_jev_undecided | اسان کي پوري پڪ ناهي، تنهن ڪري هڪ آفيسر توهان جي دعويٰ ڏسندو. | audio/sd/reason_jev_undecided.mp3 | 19.5 KB | |
| reason_low_confidence | اسان کي پوري پڪ ناهي، تنهن ڪري هڪ آفيسر توهان جي دعويٰ ڏسندو. | audio/sd/reason_low_confidence.mp3 | 19.5 KB | |
| reason_missing_death_cert | اسان کي وفات جي سرٽيفڪيٽ جي تصوير گهرجي. | audio/sd/reason_missing_death_cert.mp3 | 13.0 KB | |
| reason_missing_info | ڪجهه معلومات گهٽ آهي. مهرباني ڪري ڏيکاريل شيءِ موڪليو. | audio/sd/reason_missing_info.mp3 | 18.0 KB | |
| reason_multiple_candidates | رڪارڊ ۾ هن نالي جا هڪ کان وڌيڪ ماڻهو آهن. مهرباني ڪري مرحوم جو شناختي ڪارڊ نمبر ڏيو. | audio/sd/reason_multiple_candidates.mp3 | 26.8 KB | |
| reason_name_mismatch | توهان جي ڪاغذن تي نالو رڪارڊ سان صاف طرح نٿو ملي. مهرباني ڪري صاف تصوير موڪليو يا مددگار کي پنهنجو شناختي ڪارڊ ڏيکاريو. | audio/sd/reason_name_mismatch.mp3 | 40.1 KB | |
| reason_no_pension_record | مرحوم جي پينشن جو رڪارڊ نه مليو. هڪ آفيسر جانچ ڪندو. | audio/sd/reason_no_pension_record.mp3 | 18.6 KB | |
| reason_not_eligible | قاعدن موجب هڪ آفيسر توهان جي دعويٰ جو جائزو وٺندو. | audio/sd/reason_not_eligible.mp3 | 13.9 KB | |
| reason_not_in_family_record | خانداني رڪارڊ ۾ توهان جو نالو مرحوم سان گڏ نه مليو. هڪ آفيسر جانچ ڪندو. | audio/sd/reason_not_in_family_record.mp3 | 22.4 KB | |
| reason_payee_close_match | بئنڪ کاتي جو نالو توهان جي نالي سان پوري طرح نٿو ملي. مهرباني ڪري کاتي جي تصديق ڪريو. | audio/sd/reason_payee_close_match.mp3 | 27.4 KB | |
| reason_service_unavailable | اسان هن وقت سرڪاري رڪارڊ تائين پهچي نه سگهياسين. توهان جي دعويٰ محفوظ آهي ۽ هڪ آفيسر ان کي اڳتي وڌائيندو. | audio/sd/reason_service_unavailable.mp3 | 35.4 KB | |
| reason_time_limited | توهان جي دعويٰ منظور آهي، پر نئين قاعدي موجب هيءَ پينشن هڪ مقرر مدت تائين ملندي. | audio/sd/reason_time_limited.mp3 | 25.4 KB | |
| reason_widow_first | قاعدن موجب پهريون حق بيواهه جو آهي. هڪ آفيسر جائزو وٺندو. | audio/sd/reason_widow_first.mp3 | 20.1 KB | |
| scam_likely_scam | هي دوکو لڳي ٿو. پئسا يا ڪوڊ هرگز نه ڏيو. | audio/sd/scam_likely_scam.mp3 | 15.8 KB | |
| scam_looks_genuine | هي پيغام صحيح لڳي ٿو. پوءِ به ڪڏهن به في يا ڪوڊ نه ڏيو. | audio/sd/scam_looks_genuine.mp3 | 20.4 KB | |
| scam_not_sure | اسان کي پڪ ناهي. ڪجهه ڪرڻ کان اڳ مددگار يا آفيسر کان پڇو. | audio/sd/scam_not_sure.mp3 | 20.4 KB | |
| status_approved | توهان جي دعويٰ منظور ٿي وئي | audio/sd/status_approved.mp3 | 8.0 KB | |
| status_auto_approved | توهان جي دعويٰ منظور ٿي وئي | audio/sd/status_auto_approved.mp3 | 8.0 KB | |
| status_in_review | هڪ آفيسر توهان جي دعويٰ ڏسندو | audio/sd/status_in_review.mp3 | 8.9 KB | |
| status_proof_requested | هڪ ٻيو ڪاغذ گهرجي | audio/sd/status_proof_requested.mp3 | 6.8 KB | |
| status_rejected | آفيسر هيءَ دعويٰ منظور نه ڪئي | audio/sd/status_rejected.mp3 | 10.1 KB | |
| status_withdrawn | توهان هيءَ دعويٰ واپس ورتي | audio/sd/status_withdrawn.mp3 | 9.5 KB | |

## Punjabi (Shahmukhi)

| audioKey | Text | Clip | Size | OK / bad |
|---|---|---|---|---|
| prompt_account | پنشن کیہڑے بینک کھاتے وچ آوے؟ | audio/pa/prompt_account.mp3 | 9.2 KB | |
| prompt_deceased | مرحوم دا پورا ناں کی سی؟ | audio/pa/prompt_deceased.mp3 | 7.1 KB | |
| prompt_deceased_cnic | مرحوم دا شناختی کارڈ نمبر (جے تہانوں پتہ اے) | audio/pa/prompt_deceased_cnic.mp3 | 12.7 KB | |
| prompt_dob | تہاڈی تاریخ پیدائش کی اے؟ | audio/pa/prompt_dob.mp3 | 7.4 KB | |
| prompt_documents | تہاڈے کول کیہڑے کاغذ نیں؟ | audio/pa/prompt_documents.mp3 | 8.9 KB | |
| prompt_relation | تُسیں مرحوم دے کی لگدے او؟ | audio/pa/prompt_relation.mp3 | 6.8 KB | |
| prompt_review | دعویٰ بھیجن توں پہلاں سب کجھ ویکھ لوو | audio/pa/prompt_review.mp3 | 10.1 KB | |
| reason_account_not_owned | ایہہ بینک کھاتہ تہاڈے ناں اُتے نئیں۔ مہربانی کر کے اپنے ناں دا کھاتہ دیو۔ | audio/pa/reason_account_not_owned.mp3 | 19.2 KB | |
| reason_account_reused | ایہہ کھاتہ دوجے دعویاں وچ وی ورتیا گیا اے۔ اک افسر جانچ کرے گا۔ | audio/pa/reason_account_reused.mp3 | 17.4 KB | |
| reason_already_drawing | ریکارڈ موجب تُسیں پہلاں ای اک خاندانی پنشن لے رہے او۔ اک افسر جانچ کرے گا۔ | audio/pa/reason_already_drawing.mp3 | 24.2 KB | |
| reason_approved | تہاڈا دعویٰ منظور ہو گیا اے۔ پہلی ادائیگی چھیتی تہاڈے کھاتے وچ پہنچ جاوے گی۔ | audio/pa/reason_approved.mp3 | 22.4 KB | |
| reason_child_over_age | قاعدیاں موجب ایس عمر دے پُتر دے دعوے دا جائزہ اک افسر لوے گا۔ | audio/pa/reason_child_over_age.mp3 | 18.6 KB | |
| reason_confirm_dob | مہربانی کر کے اپنی تاریخ پیدائش دی تصدیق کرو۔ ایہہ تہاڈے شناختی کارڈ اُتے لکھی ہوئی اے۔ | audio/pa/reason_confirm_dob.mp3 | 25.1 KB | |
| reason_daughter_married | قاعدیاں موجب اک افسر دھی دے دعوے دا جائزہ لوے گا۔ | audio/pa/reason_daughter_married.mp3 | 13.9 KB | |
| reason_death_not_verified | وفات دے ریکارڈ دی حالے تصدیق نئیں ہو سکی۔ اک افسر جانچ کرے گا۔ | audio/pa/reason_death_not_verified.mp3 | 20.1 KB | |
| reason_dob_mismatch | تہاڈی دسی ہوئی تاریخ پیدائش ریکارڈ نال نئیں ملدی۔ اپنے شناختی کارڈ توں ویکھ کے دوبارہ دسو، یا مددگار نوں کارڈ وکھاؤ۔ | audio/pa/reason_dob_mismatch.mp3 | 31.4 KB | |
| reason_doc_edit_risk | تہاڈے کاغذ دی ہور جانچ ضروری اے۔ اک افسر اینوں ویکھے گا۔ | audio/pa/reason_doc_edit_risk.mp3 | 17.1 KB | |
| reason_doc_mismatch | تہاڈے کاغذ دیاں کجھ معلومات سرکاری ریکارڈ نال نئیں ملدیاں۔ مہربانی کر کے ایس کاغذ دی صاف تصویر یا دوجی کاپی بھیجو۔ | audio/pa/reason_doc_mismatch.mp3 | 35.4 KB | |
| reason_duplicate_claim | ایس پنشن لئی کسے ہور نے وی دعویٰ کیتا اے۔ اک افسر تن دناں وچ جانچ کرے گا۔ | audio/pa/reason_duplicate_claim.mp3 | 20.4 KB | |
| reason_jev_undecided | سانوں پورا یقین نئیں، ایس لئی اک افسر تہاڈا دعویٰ ویکھے گا۔ | audio/pa/reason_jev_undecided.mp3 | 16.4 KB | |
| reason_low_confidence | سانوں پورا یقین نئیں، ایس لئی اک افسر تہاڈا دعویٰ ویکھے گا۔ | audio/pa/reason_low_confidence.mp3 | 16.4 KB | |
| reason_missing_death_cert | سانوں وفات دے سرٹیفکیٹ دی تصویر چاہیدی اے۔ | audio/pa/reason_missing_death_cert.mp3 | 12.4 KB | |
| reason_missing_info | کجھ معلومات گھٹ اے۔ مہربانی کر کے دسی گئی شے بھیجو۔ | audio/pa/reason_missing_info.mp3 | 15.1 KB | |
| reason_multiple_candidates | ریکارڈ وچ ایس ناں دے اک توں ودھ بندے نیں۔ مہربانی کر کے مرحوم دا شناختی کارڈ نمبر دیو۔ | audio/pa/reason_multiple_candidates.mp3 | 24.8 KB | |
| reason_name_mismatch | تہاڈے کاغذاں اُتے ناں ریکارڈ نال صاف نئیں ملدا۔ مہربانی کر کے صاف تصویر بھیجو یا مددگار نوں اپنا شناختی کارڈ وکھاؤ۔ | audio/pa/reason_name_mismatch.mp3 | 34.2 KB | |
| reason_no_pension_record | مرحوم دی پنشن دا ریکارڈ نئیں لبھیا۔ اک افسر جانچ کرے گا۔ | audio/pa/reason_no_pension_record.mp3 | 15.8 KB | |
| reason_not_eligible | قاعدیاں موجب اک افسر تہاڈے دعوے دا جائزہ لوے گا۔ | audio/pa/reason_not_eligible.mp3 | 14.8 KB | |
| reason_not_in_family_record | خاندانی ریکارڈ وچ تہاڈا ناں مرحوم دے نال نئیں لبھیا۔ اک افسر جانچ کرے گا۔ | audio/pa/reason_not_in_family_record.mp3 | 24.2 KB | |
| reason_payee_close_match | بینک کھاتے دا ناں تہاڈے ناں نال پوری طرح نئیں ملدا۔ مہربانی کر کے کھاتے دی تصدیق کرو۔ | audio/pa/reason_payee_close_match.mp3 | 24.2 KB | |
| reason_service_unavailable | اسیں ہُنے سرکاری ریکارڈ تک نئیں اپڑ سکے۔ تہاڈا دعویٰ محفوظ اے تے اک افسر اینوں اگے ودھاوے گا۔ | audio/pa/reason_service_unavailable.mp3 | 27.1 KB | |
| reason_time_limited | تہاڈا دعویٰ منظور اے، پر نویں قاعدے موجب ایہہ پنشن اک مقررہ مدت تک ملے گی۔ | audio/pa/reason_time_limited.mp3 | 23.6 KB | |
| reason_widow_first | قاعدیاں موجب پہلا حق بیوہ دا اے۔ اک افسر جائزہ لوے گا۔ | audio/pa/reason_widow_first.mp3 | 17.4 KB | |
| scam_likely_scam | ایہہ دھوکا لگدا اے۔ پیسے یا کوڈ بالکل نہ دیو۔ | audio/pa/scam_likely_scam.mp3 | 13.3 KB | |
| scam_looks_genuine | ایہہ سنیہا ٹھیک لگدا اے۔ فیر وی کدی فیس یا کوڈ نہ دیو۔ | audio/pa/scam_looks_genuine.mp3 | 15.4 KB | |
| scam_not_sure | سانوں یقین نئیں۔ کجھ کرن توں پہلاں مددگار یا افسر کولوں پچھو۔ | audio/pa/scam_not_sure.mp3 | 19.5 KB | |
| status_approved | تہاڈا دعویٰ منظور ہو گیا | audio/pa/status_approved.mp3 | 6.8 KB | |
| status_auto_approved | تہاڈا دعویٰ منظور ہو گیا | audio/pa/status_auto_approved.mp3 | 6.8 KB | |
| status_in_review | اک افسر تہاڈا دعویٰ ویکھے گا | audio/pa/status_in_review.mp3 | 7.7 KB | |
| status_proof_requested | اک ہور کاغذ چاہیدا اے | audio/pa/status_proof_requested.mp3 | 8.0 KB | |
| status_rejected | افسر نے ایہہ دعویٰ منظور نئیں کیتا | audio/pa/status_rejected.mp3 | 8.9 KB | |
| status_withdrawn | تُسیں ایہہ دعویٰ واپس لے لیا | audio/pa/status_withdrawn.mp3 | 8.9 KB | |
