/* Launch Quality · Property photos on server (Phase 6) */
(function () {
  const MAX_BYTES = 5 * 1024 * 1024;

  function esc(s) {
    return typeof htmlEscape === "function" ? htmlEscape(s) : String(s || "");
  }

  function propertyImageUrl(p) {
    const img = String(p?.image || "").trim();
    if (!img) return null;
    if (img.startsWith("http://") || img.startsWith("https://")) return img;
    if (img.startsWith("/uploads/")) return img;
    if (img.startsWith("data:image/")) return img;
    return null;
  }

  function propertyEmojiFallback(p) {
    if (typeof lqPropertyEmoji === "function") return lqPropertyEmoji(p);
    return "🏢";
  }

  function propertyThumbHtml(p, opts = {}) {
    const hero = opts.hero;
    const url = propertyImageUrl(p);
    const emoji = propertyEmojiFallback(p);
    if (url) {
      const cls = hero ? "lq-prop-photo-wrap" : "lq-record-icon lq-prop-icon-photo";
      const imgCls = hero ? "lq-prop-photo" : "lq-prop-photo lq-prop-photo-thumb";
      const badge =
        hero && p?.status
          ? `<span class="lq-prop-photo-badge">${esc(p.status)}</span>`
          : "";
      return `<div class="${cls}">${badge}<img class="${imgCls}" src="${esc(url)}" alt="${esc(propertyLabel?.(p) || p?.name || "عقار")}" loading="lazy"></div>`;
    }
    if (hero) {
      return `<div class="lq-prop-photo-wrap"><span class="lq-prop-photo-fallback">${emoji}</span><span class="lq-prop-photo-badge">${esc(p?.status || "")}</span></div>`;
    }
    return `<span class="lq-record-icon">${emoji}</span>`;
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("تعذر قراءة الصورة"));
      reader.readAsDataURL(file);
    });
  }

  async function uploadPropertyPhoto(propertyId, file) {
    if (!propertyId || !file) return null;
    if (!file.type.startsWith("image/")) {
      throw new Error("اختر صورة JPG أو PNG أو WebP");
    }
    if (file.size > MAX_BYTES) {
      throw new Error("حجم الصورة كبير — الحد 5MB");
    }
    const image = await readFileAsDataUrl(file);
    const res = await api(`properties/${propertyId}/photo`, {
      method: "POST",
      body: JSON.stringify({ image, content_type: file.type, name: file.name }),
    });
    return res.image || res.item?.image;
  }

  function bindPropertyPhotoPreview(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    if (!input || !preview) return;
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) {
        preview.classList.add("hidden");
        preview.removeAttribute("src");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        preview.src = reader.result;
        preview.classList.remove("hidden");
      };
      reader.readAsDataURL(file);
    });
  }

  function injectEditPropertyPhoto(table, id) {
    if (table !== "properties") return;
    const row = typeof byId === "function" ? byId("properties", id) : null;
    const body = document.getElementById("genericModalBody");
    if (!body || !row) return;
    const current = propertyImageUrl(row);
    const block = document.createElement("div");
    block.className = "lq-prop-edit-photo";
    block.innerHTML = `
      <label>صورة العقار
        ${current ? `<img class="lq-prop-upload-preview" src="${esc(current)}" alt="صورة العقار">` : ""}
        <input id="lqEditPropPhoto" type="file" accept="image/jpeg,image/png,image/webp,image/gif">
        <span class="mini">تُحفظ على الخادم — JPG/PNG/WebP حتى 5MB</span>
      </label>`;
    const form = body.querySelector(".edit-form");
    if (form) form.appendChild(block);
  }

  const origEdit = window.editRecord;
  if (origEdit) {
    window.editRecord = function (table, id) {
      origEdit.apply(this, arguments);
      if (table === "properties") {
        requestAnimationFrame(() => injectEditPropertyPhoto(table, id));
      }
    };
  }

  const origSubmit = window.submitEditRecord;
  if (origSubmit) {
    window.submitEditRecord = async function (table, id) {
      const fileInput = document.getElementById("lqEditPropPhoto");
      const file = fileInput?.files?.[0];
      await origSubmit.apply(this, arguments);
      if (table === "properties" && file) {
        try {
          await uploadPropertyPhoto(id, file);
          toast("تم تحديث صورة العقار");
          if (typeof loadAll === "function") await loadAll();
        } catch (e) {
          toastErr(e);
        }
      }
    };
  }

  window.lqPropertyImageUrl = propertyImageUrl;
  window.lqPropertyThumbHtml = propertyThumbHtml;
  window.lqUploadPropertyPhoto = uploadPropertyPhoto;

  window.addEventListener("load", () => {
    bindPropertyPhotoPreview("pPhoto", "pPhotoPreview");
  });
})();
