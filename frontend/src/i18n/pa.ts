import type { Pack } from '../lib/lang'

// Punjabi in Shahmukhi (Pakistani Punjabi, Arabic script). MACHINE-ASSISTED TRANSLATION,
// TO BE REVIEWED by a native speaker. Fixed strings only, translated from the Urdu + English
// already in the app and in backend/app/decision/explanations.py. Same keys as sd.ts.
// Loaded only when someone picks Punjabi (own chunk). Audio stays Urdu.

const pa: Pack = {
  // language picker and label
  'lang.title': 'بولی',
  'lang.note': 'مشین دی مدد نال کیتا ترجمہ، حالے جانچنا باقی اے۔ آواز اردو وچ اے۔',

  // home
  'home.greeting': 'السلام علیکم',
  'home.chooseFamily': 'خاندان چنو',
  'home.newClaim': 'نواں پنشن دعویٰ',
  'home.scam': 'کی ایہہ سنیہا دھوکا اے؟',
  'home.payout': 'پنشن دا کھاتہ بدلو',
  'home.myData': 'میرا ڈیٹا تے اجازت',
  'home.myClaims': 'میرے دعوے',
  'home.claims': 'دعوے',

  // claim wizard: one question per screen
  prompt_relation: 'تُسیں مرحوم دے کی لگدے او؟',
  prompt_dob: 'تہاڈی تاریخ پیدائش کی اے؟',
  prompt_deceased: 'مرحوم دا پورا ناں کی سی؟',
  prompt_deceased_cnic: 'مرحوم دا شناختی کارڈ نمبر (جے تہانوں پتہ اے)',
  prompt_documents: 'تہاڈے کول کیہڑے کاغذ نیں؟',
  prompt_account: 'پنشن کیہڑے بینک کھاتے وچ آوے؟',
  prompt_review: 'دعویٰ بھیجن توں پہلاں سب کجھ ویکھ لوو',
  'rel.widow': 'بیوہ',
  'rel.son': 'پُتر',
  'rel.daughter': 'دھی',
  'doc.death_certificate': 'وفات دا سرٹیفکیٹ',
  'doc.claimant_cnic': 'تہاڈا شناختی کارڈ',
  'doc.frc': 'خاندانی سرٹیفکیٹ',
  'doc.nikah_nama': 'نکاح نامہ',
  'nav.back': 'پچھے',
  'nav.next': 'اگے',
  'nav.send': 'بھیجو',

  // decision headline
  'head.approved': 'تہاڈا دعویٰ منظور ہو گیا',
  'head.proof_requested': 'اک ہور کاغذ چاہیدا اے',
  'head.in_review': 'اک افسر تہاڈا دعویٰ ویکھے گا',
  'head.rejected': 'افسر نے ایہہ دعویٰ منظور نئیں کیتا',
  'head.withdrawn': 'تُسیں ایہہ دعویٰ واپس لے لیا',
  'head.saved': 'تہاڈا دعویٰ محفوظ اے',
  why: 'کیوں؟',

  // decision reasons (same codes as backend/app/decision/explanations.py)
  'reason.APPROVED': 'تہاڈا دعویٰ منظور ہو گیا اے۔ پہلی ادائیگی چھیتی تہاڈے کھاتے وچ پہنچ جاوے گی۔',
  'reason.DUPLICATE_CLAIM': 'ایس پنشن لئی کسے ہور نے وی دعویٰ کیتا اے۔ اک افسر تن دناں وچ جانچ کرے گا۔',
  'reason.NAME_MISMATCH': 'تہاڈے کاغذاں اُتے ناں ریکارڈ نال صاف نئیں ملدا۔ مہربانی کر کے صاف تصویر بھیجو یا مددگار نوں اپنا شناختی کارڈ وکھاؤ۔',
  'reason.MISSING_DEATH_CERT': 'سانوں وفات دے سرٹیفکیٹ دی تصویر چاہیدی اے۔',
  'reason.MISSING_INFO': 'کجھ معلومات گھٹ اے۔ مہربانی کر کے دسی گئی شے بھیجو۔',
  'reason.ACCOUNT_NOT_OWNED': 'ایہہ بینک کھاتہ تہاڈے ناں اُتے نئیں۔ مہربانی کر کے اپنے ناں دا کھاتہ دیو۔',
  'reason.ACCOUNT_REUSED': 'ایہہ کھاتہ دوجے دعویاں وچ وی ورتیا گیا اے۔ اک افسر جانچ کرے گا۔',
  'reason.DOC_EDIT_RISK': 'تہاڈے کاغذ دی ہور جانچ ضروری اے۔ اک افسر اینوں ویکھے گا۔',
  'reason.NOT_ELIGIBLE': 'قاعدیاں موجب اک افسر تہاڈے دعوے دا جائزہ لوے گا۔',
  'reason.JEV_UNDECIDED': 'سانوں پورا یقین نئیں، ایس لئی اک افسر تہاڈا دعویٰ ویکھے گا۔',
  'reason.LOW_CONFIDENCE': 'سانوں پورا یقین نئیں، ایس لئی اک افسر تہاڈا دعویٰ ویکھے گا۔',
  'reason.SERVICE_UNAVAILABLE': 'اسیں ہُنے سرکاری ریکارڈ تک نئیں اپڑ سکے۔ تہاڈا دعویٰ محفوظ اے تے اک افسر اینوں اگے ودھاوے گا۔',
  'reason.NOT_IN_FAMILY_RECORD': 'خاندانی ریکارڈ وچ تہاڈا ناں مرحوم دے نال نئیں لبھیا۔ اک افسر جانچ کرے گا۔',
  'reason.DEATH_NOT_VERIFIED': 'وفات دے ریکارڈ دی حالے تصدیق نئیں ہو سکی۔ اک افسر جانچ کرے گا۔',
  'reason.NO_PENSION_RECORD': 'مرحوم دی پنشن دا ریکارڈ نئیں لبھیا۔ اک افسر جانچ کرے گا۔',
  'reason.ALREADY_DRAWING': 'ریکارڈ موجب تُسیں پہلاں ای اک خاندانی پنشن لے رہے او۔ اک افسر جانچ کرے گا۔',
  'reason.CHILD_OVER_AGE': 'قاعدیاں موجب ایس عمر دے پُتر دے دعوے دا جائزہ اک افسر لوے گا۔',
  'reason.DAUGHTER_MARRIED': 'قاعدیاں موجب اک افسر دھی دے دعوے دا جائزہ لوے گا۔',
  'reason.WIDOW_FIRST': 'قاعدیاں موجب پہلا حق بیوہ دا اے۔ اک افسر جائزہ لوے گا۔',
  'reason.PAYEE_CLOSE_MATCH': 'بینک کھاتے دا ناں تہاڈے ناں نال پوری طرح نئیں ملدا۔ مہربانی کر کے کھاتے دی تصدیق کرو۔',
  'reason.TIME_LIMITED': 'تہاڈا دعویٰ منظور اے، پر نویں قاعدے موجب ایہہ پنشن اک مقررہ مدت تک ملے گی۔',
  'reason.MULTIPLE_CANDIDATES': 'ریکارڈ وچ ایس ناں دے اک توں ودھ بندے نیں۔ مہربانی کر کے مرحوم دا شناختی کارڈ نمبر دیو۔',
  'reason.CONFIRM_DOB': 'مہربانی کر کے اپنی تاریخ پیدائش دی تصدیق کرو۔ ایہہ تہاڈے شناختی کارڈ اُتے لکھی ہوئی اے۔',
  'reason.DOB_MISMATCH': 'تہاڈی دسی ہوئی تاریخ پیدائش ریکارڈ نال نئیں ملدی۔ اپنے شناختی کارڈ توں ویکھ کے دوبارہ دسو، یا مددگار نوں کارڈ وکھاؤ۔',
  'reason.DOC_MISMATCH': 'تہاڈے کاغذ دیاں کجھ معلومات سرکاری ریکارڈ نال نئیں ملدیاں۔ مہربانی کر کے ایس کاغذ دی صاف تصویر یا دوجی کاپی بھیجو۔',

  // Scam Shield verdicts
  'scam.LIKELY_SCAM': 'ایہہ دھوکا لگدا اے۔ پیسے یا کوڈ بالکل نہ دیو۔',
  'scam.NOT_SURE': 'سانوں یقین نئیں۔ کجھ کرن توں پہلاں مددگار یا افسر کولوں پچھو۔',
  'scam.LOOKS_GENUINE': 'ایہہ سنیہا ٹھیک لگدا اے۔ فیر وی کدی فیس یا کوڈ نہ دیو۔',
}

export default pa
