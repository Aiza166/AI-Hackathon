import type { Pack } from '../lib/lang'

// Sindhi (Arabic script). MACHINE-ASSISTED TRANSLATION, TO BE REVIEWED by a native speaker.
// Fixed strings only, translated from the Urdu + English already in the app and in
// backend/app/decision/explanations.py. Keys: screen strings and `reason.<CODE>`.
// Loaded only when someone picks Sindhi (own chunk). Audio stays Urdu.

const sd: Pack = {
  // language picker and label
  'lang.title': 'ٻولي',
  'lang.note': 'مشين جي مدد سان ڪيل ترجمو، اڃا جانچڻو آهي. آواز اردو ۾ آهي.',

  // home
  'home.greeting': 'السلام عليڪم',
  'home.chooseFamily': 'خاندان چونڊيو',
  'home.newClaim': 'نئين پينشن جي دعويٰ',
  'home.scam': 'ڇا هي پيغام دوکو آهي؟',
  'home.payout': 'پينشن جو کاتو بدلايو',
  'home.myData': 'منهنجو ڊيٽا ۽ اجازت',
  'home.myClaims': 'منهنجون دعوائون',
  'home.claims': 'دعوائون',

  // claim wizard: one question per screen
  prompt_relation: 'توهان مرحوم جا ڇا لڳو ٿا؟',
  prompt_dob: 'توهان جي ڄمڻ جي تاريخ ڪهڙي آهي؟',
  prompt_deceased: 'مرحوم جو پورو نالو ڇا هو؟',
  prompt_deceased_cnic: 'مرحوم جي شناختي ڪارڊ جو نمبر (جيڪڏهن ڄاڻو ٿا)',
  prompt_documents: 'توهان وٽ ڪهڙا ڪاغذ آهن؟',
  prompt_account: 'پينشن ڪهڙي بئنڪ کاتي ۾ اچي؟',
  prompt_review: 'دعويٰ موڪلڻ کان اڳ سڀ ڪجهه ڏسي وٺو',
  'rel.widow': 'بيواهه',
  'rel.son': 'پٽ',
  'rel.daughter': 'ڌيءُ',
  'doc.death_certificate': 'وفات جو سرٽيفڪيٽ',
  'doc.claimant_cnic': 'توهان جو شناختي ڪارڊ',
  'doc.frc': 'خانداني سرٽيفڪيٽ',
  'doc.nikah_nama': 'نڪاح نامو',
  'nav.back': 'واپس',
  'nav.next': 'اڳيان',
  'nav.send': 'موڪليو',

  // decision headline
  'head.approved': 'توهان جي دعويٰ منظور ٿي وئي',
  'head.proof_requested': 'هڪ ٻيو ڪاغذ گهرجي',
  'head.in_review': 'هڪ آفيسر توهان جي دعويٰ ڏسندو',
  'head.rejected': 'آفيسر هيءَ دعويٰ منظور نه ڪئي',
  'head.withdrawn': 'توهان هيءَ دعويٰ واپس ورتي',
  'head.saved': 'توهان جي دعويٰ محفوظ آهي',
  why: 'ڇو؟',

  // decision reasons (same codes as backend/app/decision/explanations.py)
  'reason.APPROVED': 'توهان جي دعويٰ منظور ٿي وئي آهي. پهرين ادائيگي جلد توهان جي کاتي ۾ پهچي ويندي.',
  'reason.DUPLICATE_CLAIM': 'هن پينشن لاءِ ڪنهن ٻئي به دعويٰ ڪئي آهي. هڪ آفيسر ٽن ڏينهن ۾ جانچ ڪندو.',
  'reason.NAME_MISMATCH': 'توهان جي ڪاغذن تي نالو رڪارڊ سان صاف طرح نٿو ملي. مهرباني ڪري صاف تصوير موڪليو يا مددگار کي پنهنجو شناختي ڪارڊ ڏيکاريو.',
  'reason.MISSING_DEATH_CERT': 'اسان کي وفات جي سرٽيفڪيٽ جي تصوير گهرجي.',
  'reason.MISSING_INFO': 'ڪجهه معلومات گهٽ آهي. مهرباني ڪري ڏيکاريل شيءِ موڪليو.',
  'reason.ACCOUNT_NOT_OWNED': 'هي بئنڪ کاتو توهان جي نالي تي ناهي. مهرباني ڪري پنهنجي نالي وارو کاتو ڏيو.',
  'reason.ACCOUNT_REUSED': 'هي کاتو ٻين دعوائن ۾ به استعمال ٿيو آهي. هڪ آفيسر جانچ ڪندو.',
  'reason.DOC_EDIT_RISK': 'توهان جي ڪاغذ جي وڌيڪ جانچ ضروري آهي. هڪ آفيسر ان کي ڏسندو.',
  'reason.NOT_ELIGIBLE': 'قاعدن موجب هڪ آفيسر توهان جي دعويٰ جو جائزو وٺندو.',
  'reason.JEV_UNDECIDED': 'اسان کي پوري پڪ ناهي، تنهن ڪري هڪ آفيسر توهان جي دعويٰ ڏسندو.',
  'reason.LOW_CONFIDENCE': 'اسان کي پوري پڪ ناهي، تنهن ڪري هڪ آفيسر توهان جي دعويٰ ڏسندو.',
  'reason.SERVICE_UNAVAILABLE': 'اسان هن وقت سرڪاري رڪارڊ تائين پهچي نه سگهياسين. توهان جي دعويٰ محفوظ آهي ۽ هڪ آفيسر ان کي اڳتي وڌائيندو.',
  'reason.NOT_IN_FAMILY_RECORD': 'خانداني رڪارڊ ۾ توهان جو نالو مرحوم سان گڏ نه مليو. هڪ آفيسر جانچ ڪندو.',
  'reason.DEATH_NOT_VERIFIED': 'وفات جي رڪارڊ جي اڃا تصديق نه ٿي سگهي. هڪ آفيسر جانچ ڪندو.',
  'reason.NO_PENSION_RECORD': 'مرحوم جي پينشن جو رڪارڊ نه مليو. هڪ آفيسر جانچ ڪندو.',
  'reason.ALREADY_DRAWING': 'رڪارڊ موجب توهان اڳ ۾ ئي هڪ خانداني پينشن وٺي رهيا آهيو. هڪ آفيسر جانچ ڪندو.',
  'reason.CHILD_OVER_AGE': 'قاعدن موجب هن عمر جي پٽ جي دعويٰ جو جائزو هڪ آفيسر وٺندو.',
  'reason.DAUGHTER_MARRIED': 'قاعدن موجب هڪ آفيسر ڌيءُ جي دعويٰ جو جائزو وٺندو.',
  'reason.WIDOW_FIRST': 'قاعدن موجب پهريون حق بيواهه جو آهي. هڪ آفيسر جائزو وٺندو.',
  'reason.PAYEE_CLOSE_MATCH': 'بئنڪ کاتي جو نالو توهان جي نالي سان پوري طرح نٿو ملي. مهرباني ڪري کاتي جي تصديق ڪريو.',
  'reason.TIME_LIMITED': 'توهان جي دعويٰ منظور آهي، پر نئين قاعدي موجب هيءَ پينشن هڪ مقرر مدت تائين ملندي.',
  'reason.MULTIPLE_CANDIDATES': 'رڪارڊ ۾ هن نالي جا هڪ کان وڌيڪ ماڻهو آهن. مهرباني ڪري مرحوم جو شناختي ڪارڊ نمبر ڏيو.',
  'reason.CONFIRM_DOB': 'مهرباني ڪري پنهنجي ڄمڻ جي تاريخ جي تصديق ڪريو. اها توهان جي شناختي ڪارڊ تي لکيل آهي.',
  'reason.DOB_MISMATCH': 'توهان جي ٻڌايل ڄمڻ جي تاريخ رڪارڊ سان نٿي ملي. پنهنجي شناختي ڪارڊ مان ڏسي ٻيهر ٻڌايو، يا مددگار کي ڪارڊ ڏيکاريو.',
  'reason.DOC_MISMATCH': 'توهان جي ڪاغذ جون ڪجهه معلومات سرڪاري رڪارڊ سان نٿيون ملن. مهرباني ڪري هن ڪاغذ جي صاف تصوير يا ٻي ڪاپي موڪليو.',

  // Scam Shield verdicts
  'scam.LIKELY_SCAM': 'هي دوکو لڳي ٿو. پئسا يا ڪوڊ هرگز نه ڏيو.',
  'scam.NOT_SURE': 'اسان کي پڪ ناهي. ڪجهه ڪرڻ کان اڳ مددگار يا آفيسر کان پڇو.',
  'scam.LOOKS_GENUINE': 'هي پيغام صحيح لڳي ٿو. پوءِ به ڪڏهن به في يا ڪوڊ نه ڏيو.',
}

export default sd
