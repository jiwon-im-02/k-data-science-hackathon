import {
  $,
  $$,
  api,
  dateTime,
  number,
  errorText,
  readDraft,
  saveDraft,
  gateBadge,
} from "./common.js";

const form = $("#orderForm");
const sample = {
  pickup: "",
  dropoff: "",
  work_time: "2026-03-18T15:00",
  weight_kg: "",
  container_type: "",
};
const fields = {
  pickup: "#pickup",
  dropoff: "#dropoff",
  work_time: "#workTime",
  weight_kg: "#weight",
};
let previewVersion = 0;
let previewTimer;
let locations = [];

function payload() {
  const result = Object.fromEntries(
    Object.entries(fields).map(([key, selector]) => {
      const input = $(selector);
      return [
        key,
        input.type === "number"
          ? input.value === ""
            ? ""
            : Number(input.value)
          : input.value.trim(),
      ];
    }),
  );
  result.container_type = $('[name="container_type"]:checked')?.value || "";
  return result;
}

function fill(values) {
  Object.entries(fields).forEach(([key, selector]) => {
    const input = $(selector);
    const value = values[key] ?? input.value;
    input.value = key === "work_time" ? String(value).slice(0, 16) : value;
  });
  $$('[name="container_type"]').forEach((input) => {
    input.checked = input.value === values.container_type;
  });
  updatePreview();
}

function showError(error) {
  const errors = error?.error;
  if (errors && typeof errors === "object") {
    Object.entries(errors).forEach(([key, message]) => {
      const node = document.querySelector(`[data-error="${key}"]`);
      if (node) node.textContent = message;
      if (fields[key]) $(fields[key]).setAttribute("aria-invalid", "true");
      if (key === "container_type") $$('[name="container_type"]').forEach((input) => input.setAttribute("aria-invalid", "true"));
    });
  }
  $("#formError").textContent = errorText(error);
  $("#formError").hidden = false;
}
function clearErrors() {
  $$(".field-error").forEach((node) => (node.textContent = ""));
  $$("[aria-invalid]").forEach((node) => node.removeAttribute("aria-invalid"));
  $("#formError").hidden = true;
}
function updatePreview() {
  const order = payload();
  $("#previewPickup").textContent = order.pickup || "상차지를 입력해주세요";
  $("#previewDropoff").textContent = order.dropoff || "하차지를 입력해주세요";
  $("#previewTime").textContent = order.work_time
    ? dateTime(order.work_time)
    : "일시 입력 필요";
  $("#previewWeight").textContent = order.weight_kg
    ? `${number(order.weight_kg)} kg`
    : "중량 입력 필요";
  clearTimeout(previewTimer);
  const version = ++previewVersion;
  $("#gateBadge").className = "badge neutral";
  $("#gateBadge").textContent = "확인 중";
  $("#containerType").textContent = order.container_type || "선택 필요";
  $("#containerReason").textContent = "지정한 컨테이너의 중량 기준을 확인하고 있습니다.";
  $("#gateMessage").textContent = "";
  if (!order.container_type) {
    $("#gateBadge").textContent = "선택 필요";
    $("#containerReason").textContent = "요청서에 지정된 컨테이너 타입을 선택해주세요.";
    return;
  }
  previewTimer = setTimeout(() => previewContainer(version), 250);
}
async function previewContainer(version) {
  try {
    const result = await api("/api/container", {
      method: "POST",
      body: JSON.stringify(payload()),
    });
    if (version !== previewVersion) return;
    renderContainer(result);
  } catch {
    if (version !== previewVersion) return;
    $("#gateBadge").textContent = "입력 필요";
    $("#containerReason").textContent =
      "컨테이너 타입과 필수 운송 정보를 확인해주세요.";
  }
}
function renderContainer(data) {
  $("#gateBadge").outerHTML = gateBadge(data.gate.status).replace(
    "<span ",
    '<span id="gateBadge" ',
  );
  $("#containerType").textContent = data.container.container_type;
  $("#containerReason").textContent = data.container.reason;
  $("#gateMessage").textContent =
    data.gate.status === "OK" ? "" : data.gate.message;
}
function reviewGate(data, order) {
  const dialog = $("#gateDialog");
  const warning = data.gate.status === "WARN";
  const weight = Number(order.weight_kg);
  const blockLimit = Number(data.gate.block_kg);
  const warnLimit = data.gate.warn_kg;

  dialog.classList.toggle("warn", warning);
  dialog.classList.toggle("block", !warning);
  $("#gateDialogBadge").innerHTML = gateBadge(data.gate.status);
  $("#gateDialogTitle").textContent = warning
    ? "과적 주의 구간입니다"
    : "허용 중량을 초과했습니다";
  $("#gateDialogMessage").textContent = data.gate.message;
  $("#gateDialogContainer").textContent = data.container.container_type;
  $("#gateDialogWeight").textContent = number(weight) + " kg";
  $("#gateDialogLimit").textContent = number(blockLimit) + " kg 미만";
  $("#gateDialogWarnLimit").textContent =
    warnLimit === null ? "경고 구간 없음" : number(warnLimit) + " kg 이상";

  if (warning) {
    const remaining = Math.max(blockLimit - weight, 0);
    $("#gateDialogDelta").textContent =
      "BLOCK 기준까지 " + number(remaining) + " kg 남았습니다.";
  } else {
    const excess = Math.max(weight - blockLimit, 0);
    $("#gateDialogDelta").textContent =
      excess > 0
        ? "허용 기준보다 " + number(excess) + " kg 초과했습니다."
        : "현재 중량이 BLOCK 기준에 도달했습니다.";
  }

  $("#continueWarning").hidden = !warning;
  dialog.showModal();
  $(warning ? "#continueWarning" : "#editGateInput").focus();

  return new Promise((resolve) => {
    let settled = false;
    const finish = (proceed) => {
      if (settled) return;
      settled = true;
      dialog.close();
      resolve(proceed);
    };
    $("#editGateInput").onclick = () => finish(false);
    $("#continueWarning").onclick = () => finish(true);
    dialog.onclose = () => {
      if (!settled) {
        settled = true;
        resolve(false);
      }
    };
  });
}

form.addEventListener("input", updatePreview);
form.addEventListener("change", updatePreview);
$("#swapLocations").addEventListener("click", () => {
  const pickup = $("#pickup").value;
  $("#pickup").value = $("#dropoff").value;
  $("#dropoff").value = pickup;
  updatePreview();
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  const order = payload();
  // Exact list matching avoids silently assigning a similarly named OD location.
  const errors = {};
  for (const key of ["pickup", "dropoff"]) {
    if (locations.length && !locations.includes(order[key]))
      errors[key] = "목록에 있는 운송 거점을 선택해주세요.";
  }
  if (order.pickup === order.dropoff)
    errors.dropoff = "상차지와 하차지는 달라야 합니다.";
  if (Object.keys(errors).length) {
    showError({ error: errors });
    form.querySelector("[aria-invalid]")?.focus();
    return;
  }
  const button = $("#recommendButton");
  button.disabled = true;
  button.textContent = "운송 조건 확인 중…";
  // Invalidate older preview responses before the definitive weight check.
  ++previewVersion;
  clearTimeout(previewTimer);
  try {
    const result = await api("/api/container", {
      method: "POST",
      body: JSON.stringify(order),
    });
    renderContainer(result);
    if (result.gate.status === "BLOCK") {
      await reviewGate(result, order);
      $("#weight").focus();
      return;
    }
    if (result.gate.status === "WARN") {
      const proceed = await reviewGate(result, order);
      if (!proceed) return;
    }
    saveDraft(order);
    window.location.assign("/recommendations");
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
    button.textContent = "추천 차량 조회 →";
  }
});

// Browser Back/forward cache must not restore a disabled submit button.
window.addEventListener("pageshow", () => {
  $("#recommendButton").disabled = false;
});
fill(
  new URLSearchParams(location.search).has("edit")
    ? readDraft() || sample
    : sample,
);
try {
  const data = await api("/api/bootstrap");
  locations = data.locations;
  $("#locations").replaceChildren(
    ...locations.map((name) => {
      const option = document.createElement("option");
      option.value = name;
      return option;
    }),
  );
  $("#slackRule").textContent =
    `${data.model.minimum_arrival_slack_min}분 이상`;
  $("#gapRule").textContent = `${data.model.maximum_work_gap_h}시간 이내`;
} catch (error) {
  showError(error);
}
