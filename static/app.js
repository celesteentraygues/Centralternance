"use strict";

const SESSION_KEY = "centralternance.session";
const $ = (id) => document.getElementById(id);

// ---------- Session (navigateur uniquement) ----------

function loadSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* mode privé strict : on continue en mémoire seulement */
  }
}

const state = {
  session: loadSession(),
  pendingCV: null,     // { text, truncated } uploadé mais pas encore validé par "Commencer"
  lastType: null,      // "lettre" | "spontane"
  lastBody: null,      // dernière requête envoyée à /api/generate (pour Réessayer)
};

// ---------- Navigation ----------

function show(name) {
  document.querySelectorAll(".screen").forEach((s) => {
    s.hidden = s.id !== `screen-${name}`;
  });
  $("btn-menu").hidden = name === "onboarding" || name === "menu";
  window.scrollTo(0, 0);
}

// ---------- Appels API ----------

async function api(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("Connexion impossible. Vérifiez votre réseau et réessayez.");
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* réponse sans JSON */
  }
  if (!res.ok) {
    const detail = body && body.detail;
    throw new Error(typeof detail === "string" ? detail : "Erreur inattendue, réessayez.");
  }
  return body;
}

function setLoading(btn, on, label) {
  btn.disabled = on;
  btn.classList.toggle("loading", on);
  if (on) {
    btn.dataset.label = btn.textContent;
    btn.textContent = label;
  } else if (btn.dataset.label) {
    btn.textContent = btn.dataset.label;
  }
}

function showError(el, message, onRetry) {
  el.textContent = message + " ";
  if (onRetry) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "link";
    retry.textContent = "Réessayer";
    retry.addEventListener("click", onRetry);
    el.appendChild(retry);
  }
  el.hidden = false;
}

function clearError(el) {
  el.textContent = "";
  el.hidden = true;
}

// ---------- Écran 1 : onboarding ----------

function fillOnboardingFromSession() {
  const s = state.session;
  const status = $("cv-status");
  if (s && s.cv) {
    $("cs-rythme").value = s.cs.rythme;
    $("cs-debut").value = s.cs.debut;
    $("cs-duree").value = s.cs.duree;
    $("modele").value = s.modele || "";
    status.textContent = "CV chargé : conservé (choisissez un fichier pour le remplacer).";
    status.className = "status ok";
  } else {
    status.textContent = "";
    status.className = "status";
  }
  $("cv-file").value = "";
  state.pendingCV = null;
  updateStartButton();
}

function updateStartButton() {
  const hasCV = Boolean(state.pendingCV || (state.session && state.session.cv));
  $("btn-start").disabled = !hasCV;
}

$("cv-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  const status = $("cv-status");
  state.pendingCV = null;
  updateStartButton();
  if (!file) return;

  status.textContent = "Lecture du CV…";
  status.className = "status";
  const form = new FormData();
  form.append("file", file);
  try {
    const parsed = await api("/api/parse-cv", { method: "POST", body: form });
    state.pendingCV = { text: parsed.text, truncated: parsed.truncated };
    status.textContent = parsed.truncated
      ? "CV lu (très long : seules les premières pages seront utilisées)."
      : "CV lu avec succès.";
    status.className = "status ok";
  } catch (err) {
    status.textContent = err.message;
    status.className = "status error";
    event.target.value = "";
  }
  updateStartButton();
});

$("form-onboarding").addEventListener("submit", (event) => {
  event.preventDefault();
  const cv = state.pendingCV || { text: state.session.cv, truncated: state.session.truncated };
  state.session = {
    cv: cv.text,
    truncated: cv.truncated,
    cs: {
      rythme: $("cs-rythme").value.trim(),
      debut: $("cs-debut").value.trim(),
      duree: $("cs-duree").value.trim(),
    },
    modele: $("modele").value.trim(),
  };
  saveSession(state.session);
  state.pendingCV = null;
  show("menu");
});

// ---------- Écran 2 : menu ----------

$("card-offre").addEventListener("click", () => openOffre());
$("card-spontane").addEventListener("click", () => openSpontane());
$("link-edit-profile").addEventListener("click", () => {
  fillOnboardingFromSession();
  show("onboarding");
});
$("btn-menu").addEventListener("click", () => show("menu"));

// ---------- Écran 3 : offre ----------

function openOffre() {
  $("offre").value = "";
  clearError($("err-offre"));
  $("btn-gen-lettre").disabled = true;
  show("offre");
  $("offre").focus();
}

$("offre").addEventListener("input", () => {
  $("btn-gen-lettre").disabled = $("offre").value.trim() === "";
});

$("form-offre").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {
    type: "lettre",
    cv: state.session.cv,
    cs: state.session.cs,
    modele: state.session.modele,
    offre: $("offre").value.trim(),
  };
  runGeneration(body, $("btn-gen-lettre"), $("err-offre"));
});

// ---------- Écran 4 : spontané ----------

const contactFields = ["c-nom", "c-entreprise", "c-poste-contact", "c-poste-vise"];

function openSpontane() {
  contactFields.forEach((id) => { $(id).value = ""; });
  clearError($("err-spontane"));
  $("btn-gen-spontane").disabled = true;
  show("spontane");
  $("c-nom").focus();
}

function updateSpontaneButton() {
  const complete = contactFields.every((id) => $(id).value.trim() !== "");
  $("btn-gen-spontane").disabled = !complete;
}
contactFields.forEach((id) => $(id).addEventListener("input", updateSpontaneButton));

$("form-spontane").addEventListener("submit", (event) => {
  event.preventDefault();
  const body = {
    type: "spontane",
    cv: state.session.cv,
    cs: state.session.cs,
    modele: state.session.modele,
    contact: {
      nom: $("c-nom").value.trim(),
      entreprise: $("c-entreprise").value.trim(),
      poste_contact: $("c-poste-contact").value.trim(),
      poste_vise: $("c-poste-vise").value.trim(),
    },
  };
  runGeneration(body, $("btn-gen-spontane"), $("err-spontane"));
});

// ---------- Génération commune ----------

async function runGeneration(body, btn, errEl) {
  clearError(errEl);
  setLoading(btn, true, "Génération en cours…");
  state.lastType = body.type;
  state.lastBody = body;
  try {
    const result = await api("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    showResult(body.type, result);
  } catch (err) {
    showError(errEl, err.message, () => runGeneration(body, btn, errEl));
  } finally {
    setLoading(btn, false);
  }
}

// ---------- Écran 5 : résultat ----------

function showResult(type, result) {
  const isLettre = type === "lettre";
  $("result-lettre").hidden = !isLettre;
  $("result-spontane").hidden = isLettre;
  if (isLettre) {
    $("lettre-text").value = result.lettre;
  } else {
    $("objet-text").value = result.objet;
    $("email-text").value = result.email;
    $("linkedin-text").value = result.linkedin;
  }
  show("resultat");
}

async function copyFrom(inputId, btn) {
  const text = $(inputId).value;
  const original = btn.textContent;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Copié !";
  } catch {
    $(inputId).select();
    document.execCommand("copy");
    btn.textContent = "Copié !";
  }
  setTimeout(() => { btn.textContent = original; }, 1500);
}

$("btn-copy-lettre").addEventListener("click", (e) => copyFrom("lettre-text", e.currentTarget));
$("btn-copy-objet").addEventListener("click", (e) => copyFrom("objet-text", e.currentTarget));
$("btn-copy-email").addEventListener("click", (e) => copyFrom("email-text", e.currentTarget));
$("btn-copy-linkedin").addEventListener("click", (e) => copyFrom("linkedin-text", e.currentTarget));

$("btn-print").addEventListener("click", () => {
  $("print-area").textContent = $("lettre-text").value;
  window.print();
});

$("btn-new").addEventListener("click", () => {
  if (state.lastType === "spontane") openSpontane();
  else openOffre();
});

// ---------- Démarrage ----------

if (state.session && state.session.cv) {
  show("menu");
} else {
  fillOnboardingFromSession();
  show("onboarding");
}
