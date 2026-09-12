/* =========================================================================
   ফসল বন্ধু — গুগল শীট থেকে লাইভ ডেটা লোডার
   শীটটা "Anyone with the link can view" হিসেবে শেয়ার করা থাকলে এটা কাজ করবে।
   শীটে নতুন সারি যোগ করলে অ্যাপ রিলোড দিলেই সেটা দেখা যাবে — কোনো ব্যাকএন্ড লাগবে না।
   ========================================================================= */

// আপনার শীটের আইডি (URL থেকে নেওয়া)
const SHEET_ID = "1aDrWUM8Up6FDnu24QO8GSn_qJ5iqnzOXgfA1uyJ-vMA";
// শীটের প্রথম ট্যাব ধরে নেওয়া হয়েছে (gid=0)। শীটে একাধিক ট্যাব থাকলে এবং
// ভিন্ন ট্যাব থেকে ডেটা লাগলে, সেই ট্যাব খুলে URL-এর শেষে #gid=XXXXXX
// দেখে এখানে বসিয়ে দিন।
const SHEET_GID = "0";
const CSV_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/export?format=csv&gid=${SHEET_GID}`;

// ---------- ১. RFC4180-ঘেঁষা সাধারণ CSV পার্সার (কোটেড কমা/নিউলাইন হ্যান্ডল করে) ----------
function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (ch === '"' && next === '"') { field += '"'; i++; }
      else if (ch === '"') { inQuotes = false; }
      else { field += ch; }
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === ',') { row.push(field); field = ""; }
      else if (ch === '\n') { row.push(field); rows.push(row); row = []; field = ""; }
      else if (ch === '\r') { /* ignore, \n হ্যান্ডল করবে */ }
      else field += ch;
    }
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.some((c) => c && c.trim() !== ""));
}

// ---------- ২. "কীটনাশক (Insecticide)" ফরম্যাট থেকে বাংলা+ইংরেজি আলাদা করা ----------
function splitCategory(raw) {
  if (!raw) return { bn: "", en: "" };
  const m = raw.match(/^(.*?)\s*\(([^)]+)\)\s*$/);
  if (m) return { bn: m[1].trim(), en: m[2].trim() };
  return { bn: raw.trim(), en: raw.trim() };
}

// ---------- ৩. CSV সারিগুলোকে অ্যাপের ডেটা ফরম্যাটে রূপান্তর ----------
// কলাম ধরে নেওয়া হয়েছে: ক্রমিক নং | কোম্পানীর নাম | ব্র্যান্ড/ওষুধের নাম |
//                        সক্রিয় উপাদান | বালাইনাশকের ধরণ | প্রস্তুত প্রণালী | প্রয়োগ ক্ষেত্র ও কাজ
// শীটের কলাম অর্ডার বদলে গেলে এখানের ইনডেক্স (row[0], row[1]...) বদলাতে হবে।
function rowsToRecords(rows) {
  const records = [];
  let id = 1;
  // প্রথম সারি হেডার হতে পারে — "ক্রমিক" বা "কোম্পানী" শব্দ থাকলে স্কিপ করা হচ্ছে
  const startIdx = /ক্রমিক|কোম্পানী|company/i.test(rows[0]?.join(" ") || "") ? 1 : 0;

  for (let i = startIdx; i < rows.length; i++) {
    const r = rows[i];
    if (!r || r.length < 4) continue;
    const company = (r[1] || "").trim();
    const brand = (r[2] || "").trim();
    const activeIngredient = (r[3] || "").trim();
    const categoryRaw = (r[4] || "").trim();
    const formulation = (r[5] || "").trim();
    const useCase = (r[6] || "").trim();

    if (!brand && !activeIngredient) continue; // খালি সারি বাদ

    const { bn, en } = splitCategory(categoryRaw);
    records.push({
      id: id++,
      company, brand, activeIngredient,
      categoryBn: bn, categoryEn: en,
      formulation, useCase,
    });
  }
  return records;
}

// ---------- ৪. মূল লোডার — লাইভ শীট থেকে আনার চেষ্টা, ব্যর্থ হলে বান্ডিল করা ডেটায় ফিরে যাওয়া ----------
async function loadPesticideData(onStatus) {
  try {
    onStatus && onStatus("লাইভ শীট থেকে ডেটা আনা হচ্ছে...");
    const res = await fetch(CSV_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const text = await res.text();
    const rows = parseCSV(text);
    const records = rowsToRecords(rows);

    if (records.length === 0) throw new Error("শীট থেকে কোনো ডেটা পার্স করা যায়নি");

    onStatus && onStatus(null);
    return { data: records, source: "live", count: records.length };
  } catch (err) {
    console.warn("লাইভ শীট লোড ব্যর্থ, বান্ডিল করা ডেটা ব্যবহার হচ্ছে:", err.message);
    onStatus && onStatus(null);
    return { data: (typeof FALLBACK_DATA !== "undefined" ? FALLBACK_DATA : []), source: "fallback", count: (typeof FALLBACK_DATA !== "undefined" ? FALLBACK_DATA.length : 0) };
  }
}
