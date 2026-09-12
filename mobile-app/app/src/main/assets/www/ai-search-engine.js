/* =========================================================================
   ফসল বন্ধু — সার্চ ইঞ্জিন (ফাজি ম্যাচিং + বাংলা↔ইংরেজি ফোনেটিক ট্রান্সলিটারেশন)
   এটা একটা প্রোটোটাইপ-লেভেল ইমপ্লিমেন্টেশন — ভবিষ্যতে আসল NLP/embedding
   মডেল দিয়ে রিপ্লেস করা যাবে (নিচে README-তে বিস্তারিত)
   ========================================================================= */

// ---------- ১. বাংলা → ল্যাটিন ফোনেটিক ট্রান্সলিটারেশন ম্যাপ ----------
const BN_TO_LATIN = {
  "অ": "a", "আ": "a", "ই": "i", "ঈ": "i", "উ": "u", "ঊ": "u", "ঋ": "ri",
  "এ": "e", "ঐ": "oi", "ও": "o", "ঔ": "ou",
  "ক": "k", "খ": "kh", "গ": "g", "ঘ": "gh", "ঙ": "ng",
  "চ": "ch", "ছ": "chh", "জ": "j", "ঝ": "jh", "ঞ": "n",
  "ট": "t", "ঠ": "th", "ড": "d", "ঢ": "dh", "ণ": "n",
  "ত": "t", "থ": "th", "দ": "d", "ধ": "dh", "ন": "n",
  "প": "p", "ফ": "ph", "ব": "b", "ভ": "bh", "ম": "m",
  "য": "j", "র": "r", "ল": "l", "শ": "sh", "ষ": "sh", "স": "s", "হ": "h",
  "ড়": "r", "ঢ়": "rh", "য়": "y", "ৎ": "t",
  "ং": "ng", "ঃ": "h", "ঁ": "",
  "া": "a", "ি": "i", "ী": "i", "ু": "u", "ূ": "u", "ৃ": "ri",
  "ে": "e", "ৈ": "oi", "ো": "o", "ৌ": "ou",
  "্": "", "়": "",
  "০":"0","১":"1","২":"2","৩":"3","৪":"4","৫":"5","৬":"6","৭":"7","৮":"8","৯":"9",
};

function transliterate(text) {
  if (!text) return "";
  let out = "";
  for (const ch of text) {
    if (BN_TO_LATIN.hasOwnProperty(ch)) out += BN_TO_LATIN[ch];
    else out += ch;
  }
  return out.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function hasBangla(text) {
  return /[\u0980-\u09FF]/.test(text);
}

// ---------- ২. Levenshtein দূরত্ব + সাদৃশ্য অনুপাত ----------
function levenshtein(a, b) {
  if (a === b) return 0;
  const al = a.length, bl = b.length;
  if (al === 0) return bl;
  if (bl === 0) return al;
  const dp = new Array(bl + 1);
  for (let j = 0; j <= bl; j++) dp[j] = j;
  for (let i = 1; i <= al; i++) {
    let prev = dp[0];
    dp[0] = i;
    for (let j = 1; j <= bl; j++) {
      const tmp = dp[j];
      dp[j] = Math.min(
        dp[j] + 1,
        dp[j - 1] + 1,
        prev + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
      prev = tmp;
    }
  }
  return dp[bl];
}

function similarity(a, b) {
  if (!a || !b) return 0;
  const maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 1;
  return 1 - levenshtein(a, b) / maxLen;
}

// ---------- ৩. একটা ফিল্ডের সাথে কোয়েরির স্কোর বের করা ----------
// পুরো ফিল্ড টেক্সটে সাবস্ট্রিং মিলে গেলে বেশি স্কোর; নাহলে শব্দ-ভিত্তিক ফাজি মিল
function fieldScore(query, fieldPhonetic) {
  if (!fieldPhonetic) return 0;
  if (!query) return 0;

  if (fieldPhonetic.includes(query)) {
    // সরাসরি সাবস্ট্রিং মিল — খুব শক্তিশালী সিগন্যাল
    const coverage = query.length / fieldPhonetic.length;
    return 88 + Math.min(12, coverage * 40);
  }

  const words = fieldPhonetic.split(" ").filter(Boolean);
  let best = 0;
  for (const w of words) {
    const s = similarity(query, w) * 100;
    if (s > best) best = s;
    // কোয়েরি শব্দের শুরুর সাথে মিললে বোনাস (যেমন "fip" -> "fipronil")
    if (w.startsWith(query) && query.length >= 3) {
      best = Math.max(best, 70 + (query.length / w.length) * 25);
    }
  }
  // পুরো স্ট্রিং লেভেলেও একবার চেক (মাল্টি-ওয়ার্ড কোয়েরির জন্য)
  const wholeSim = similarity(query, fieldPhonetic) * 100;
  return Math.max(best, wholeSim * 0.85);
}

// ---------- ৪. প্রতিটা রেকর্ডের জন্য ফোনেটিক ইনডেক্স তৈরি ----------
function buildIndex(data) {
  return data.map((rec) => ({
    ...rec,
    _idx: {
      brand: transliterate(rec.brand),
      company: transliterate(rec.company),
      activeIngredient: transliterate(rec.activeIngredient),
      categoryBn: transliterate(rec.categoryBn),
      categoryEn: transliterate(rec.categoryEn),
      formulation: transliterate(rec.formulation),
      useCase: transliterate(rec.useCase),
    },
  }));
}

// প্রতিটা ফিল্ডের গুরুত্ব (ওয়েট) — সক্রিয় উপাদান ও ব্র্যান্ড নাম সবচেয়ে গুরুত্বপূর্ণ
const FIELD_WEIGHTS = {
  activeIngredient: 1.0,
  brand: 0.95,
  useCase: 0.9,
  categoryBn: 0.75,
  categoryEn: 0.75,
  company: 0.5,
  formulation: 0.4,
};

// ---------- ৫. মূল সার্চ ফাংশন ----------
function search(indexedData, rawQuery, categoryFilter) {
  const query = transliterate(hasBangla(rawQuery) ? rawQuery : rawQuery.toLowerCase());
  if (!query) return { results: [], suggestions: [], bestScore: 0 };

  const scored = indexedData.map((rec) => {
    let bestField = null;
    let bestFieldScore = 0;
    for (const key in FIELD_WEIGHTS) {
      const s = fieldScore(query, rec._idx[key]) * FIELD_WEIGHTS[key];
      if (s > bestFieldScore) {
        bestFieldScore = s;
        bestField = key;
      }
    }
    return { rec, score: Math.round(bestFieldScore), matchedField: bestField };
  });

  scored.sort((a, b) => b.score - a.score);
  const bestScore = scored.length ? scored[0].score : 0;

  let filtered = scored;
  if (categoryFilter && categoryFilter !== "all") {
    filtered = scored.filter((s) => s.rec.categoryEn.toLowerCase() === categoryFilter);
  }

  const CONFIDENT = 68;
  const POSSIBLE = 32;

  if (bestScore >= CONFIDENT) {
    const results = filtered.filter((s) => s.score >= 40).slice(0, 30);
    return { results, suggestions: [], bestScore, fallback: false };
  } else if (bestScore >= POSSIBLE) {
    // নিশ্চিত না — "আপনি কি এটি খুঁজছেন?" সাজেশন হিসেবে টপ ৩-৪টা ইউনিক টার্ম দেখানো
    const seen = new Set();
    const suggestions = [];
    for (const s of scored) {
      const label =
        s.matchedField === "activeIngredient" ? s.rec.activeIngredient :
        s.matchedField === "brand" ? s.rec.brand :
        s.matchedField === "useCase" ? s.rec.useCase :
        s.matchedField === "categoryBn" ? s.rec.categoryBn :
        s.matchedField === "categoryEn" ? s.rec.categoryEn :
        s.rec.company;
      if (!seen.has(label) && s.score >= POSSIBLE) {
        seen.add(label);
        suggestions.push({ label, score: s.score });
      }
      if (suggestions.length >= 4) break;
    }
    return { results: [], suggestions, bestScore, fallback: false };
  } else {
    // একদমই কিছু না মিললেও, একেবারে খালি না দেখিয়ে সবচেয়ে কাছাকাছি ৩টা দেখানো হচ্ছে
    const closest = filtered.slice(0, 3).filter((s) => s.score > 0);
    return { results: closest, suggestions: [], bestScore, fallback: true };
  }
}
