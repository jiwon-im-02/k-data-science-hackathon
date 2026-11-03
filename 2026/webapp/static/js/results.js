import {
  $,
  $$,
  api,
  number,
  dateTime,
  clockTime,
  duration,
  escapeHTML as esc,
  errorText,
  readDraft,
  saveDraft,
  gateBadge,
  ownerBadge,
  toast,
} from "./common.js";
import { RouteView } from "./route-map.js";

const state = {
  order: readDraft(),
  result: null,
  selected: null,
  filter: "all",
  map: null,
  confirmed: false,
};
const TARGET_SLACK_MIN = 25;
const svgCheck =
  '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
const detail = (label, value) =>
  `<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;

function renderSummary(result) {
  const order = result.order;
  $("#orderPickup").textContent = order.pickup_rep;
  $("#orderDropoff").textContent = order.dropoff_rep;
  $("#orderTime").textContent = dateTime(order.order_time);
  $("#orderCargo").textContent =
    [order.container_type, `${number(order.weight_kg)} kg`, order.cargo_type].filter(Boolean).join(" · ");
  $("#resultGate").outerHTML = gateBadge(result.gate.status).replace(
    "<span ",
    '<span id="resultGate" ',
  );
  $("#warningBanner").hidden = result.gate.status !== "WARN";
  $("#warningText").textContent = result.gate.message;
  $("#loadedDistance").textContent = `${number(order.loaded_distance_km)} km`;
  $("#loadedTime").textContent = duration(order.loaded_time_min);
  $("#candidateCount").textContent =
    `${number(result.candidates.length)}`;
  $("#allCount").textContent = result.candidates.length;
  $("#ownCount").textContent = result.candidates.filter(
    (v) => v.owner_type === "자차",
  ).length;
  $("#charterCount").textContent = result.candidates.filter(
    (v) => v.owner_type === "용차",
  ).length;
}

function reason(candidate) {
  const minimum = state.result.candidates[0]?.empty_distance_km;
  const distanceReason =
    candidate.empty_distance_km === 0
      ? "상차 거점에 위치하여 공차 이동이 없습니다."
      : candidate.empty_distance_km === minimum
        ? "적합 후보 중 상차지까지 공차거리가 가장 짧습니다."
        : `상차지까지 ${number(candidate.empty_distance_km)} km 이동으로 운송이 가능합니다.`;
  return `${esc(distanceReason)} <b>${esc(duration(candidate.arrival_slack_min))}의 도착 여유</b>를 확보합니다.`;
}

function card(candidate) {
  const active = state.selected?.vehicle_id === candidate.vehicle_id;
  return `<article class="candidate-card${candidate.rank === 1 ? " top" : ""}${active ? " selected" : ""}" data-vehicle="${esc(candidate.vehicle_id)}">
    ${candidate.rank === 1 ? `<div class="top-rank-strip">${svgCheck}최우선 추천</div>` : ""}
    <div class="candidate-main">
      <div class="candidate-head"><div class="candidate-identity"><span class="rank-num" aria-label="추천 ${candidate.rank}순위">${candidate.rank}</span><strong class="vehicle-name">${esc(candidate.vehicle_id)}</strong>${ownerBadge(candidate.owner_type)}</div><span class="vehicle-status">${esc(candidate.status)}</span></div>
      <div class="current-location">현재 위치 <b>${esc(candidate.current_location)}</b></div>
      <div class="candidate-metrics">
        <div><span>예상 공차거리</span><strong>${number(candidate.empty_distance_km)}<small>km</small></strong></div>
        <div><span>공차 이동시간</span><strong>${number(candidate.empty_time_min)}<small>분</small></strong></div>
        <div><span>상차지 도착 예정</span><strong class="eta">${esc(clockTime(candidate.estimated_arrival_time))}</strong><small class="date-label">${esc(dateTime(candidate.estimated_arrival_time).split(" ").slice(0, 2).join(" "))}</small></div>
      </div>
      <p class="candidate-reason">${reason(candidate)}</p>
      <div class="candidate-schedule">이후 예정 배차 · 별도 확인 필요</div>
      <div class="candidate-footer"><span>추천 순위 · ${candidate.rank}순위 / 적합 ${number(state.result.feasible_candidate_count)}대</span><button class="select-button" type="button" data-select="${esc(candidate.vehicle_id)}" aria-pressed="${active}" aria-label="${esc(candidate.vehicle_id)} 배차 선택">${active ? "✓ 선택됨" : "배차 선택"}</button></div>
    </div>
    <details class="candidate-details"><summary>가용 상태 및 추천 상세</summary><dl>
      ${detail("현재 작업", candidate.current_route || "진행 중인 확정 작업 없음")}
      ${detail("현재 작업 종료 예정", dateTime(candidate.current_finish_time))}
      ${detail("운송 가능 시각", dateTime(candidate.available_time))}
      ${detail("도착 여유시간", duration(candidate.arrival_slack_min))}
      ${detail("예상 운송 완료", dateTime(candidate.estimated_finish_time))}
      ${detail("추천 기준", `공차거리 → 도착 여유 ${TARGET_SLACK_MIN}분에 가까운 순`)}
    </dl></details>
  </article>`;
}

function renderCandidates() {
  const candidates = state.result.candidates.filter(
    (v) => state.filter === "all" || v.owner_type === state.filter,
  );
  $("#candidateList").innerHTML = candidates.map(card).join("");
  $("#emptyState").hidden = Boolean(candidates.length);
  if (!candidates.length) {
    const excluded = state.result.excluded_reasons || {};
    $("#emptyTitle").textContent = state.result.candidates.length
      ? "이 구분의 추천 차량이 없습니다"
      : "운행 조건을 충족하는 차량이 없습니다";
    $("#emptyText").textContent = state.result.candidates.length
      ? "표시된 상위 후보에 해당 구분의 차량이 없습니다. 전체 탭에서 다른 후보를 확인해주세요."
      : `일시 또는 상차 거점을 조정해 다시 조회해주세요. 가용 시각 조건 초과·미충족 ${number(excluded.work_gap_fail)}대, 도착 여유 미달 ${number(excluded.arrival_slack_fail)}대, 이력 없음 ${number(excluded.state_unknown)}대, 이동 데이터 없음 ${number(excluded.pickup_od_missing)}대.`;
  }
  $$("[data-select]").forEach((button) =>
    button.addEventListener("click", () =>
      selectCandidate(button.dataset.select),
    ),
  );
}

function selectCandidate(vehicleId) {
  if (state.confirmed) return;
  state.selected =
    state.result.candidates.find((v) => v.vehicle_id === vehicleId) || null;
  $$(".candidate-card").forEach((card) =>
    card.classList.toggle("selected", card.dataset.vehicle === vehicleId),
  );
  $$("[data-select]").forEach((button) => {
    const selected = button.dataset.select === vehicleId;
    button.setAttribute("aria-pressed", String(selected));
    button.textContent = selected ? "✓ 선택됨" : "배차 선택";
  });
  $("#dispatchDock").hidden = !state.selected;
  $("#emptyDistance").textContent = state.selected
    ? `${number(state.selected.empty_distance_km)} km`
    : "차량 선택 전";
  $("#emptyTime").textContent = state.selected
    ? duration(state.selected.empty_time_min)
    : "";
  if (state.selected) {
    $("#selectedVehicle").textContent =
      `${state.selected.vehicle_id} · ${state.selected.owner_type}`;
    $("#selectedArrival").textContent = dateTime(
      state.selected.estimated_arrival_time,
    );
  }
  renderItinerary();
  state.map?.show(state.result, state.selected);
}

function renderItinerary() {
  const vehicle = state.selected;
  const order = state.result.order;
  $("#routeItinerary").innerHTML =
    `${vehicle ? `<div class="itinerary-row"><span class="route-node vehicle-node">차</span><div><strong>${esc(vehicle.current_location)}</strong><small>${esc(vehicle.vehicle_id)}</small></div><time>${esc(dateTime(vehicle.available_time))} 가용</time></div>` : ""}
    <div class="itinerary-row"><span class="route-node pickup-node">상</span><div><strong>${esc(order.pickup_rep)}</strong><small>상차 예정</small></div><time>${esc(dateTime(order.order_time))}</time></div>
    <div class="itinerary-row"><span class="route-node dropoff-node">하</span><div><strong>${esc(order.dropoff_rep)}</strong><small>하차 거점</small></div><time>${vehicle ? esc(dateTime(vehicle.estimated_finish_time)) + " 완료 예정" : ""}</time></div>`;
}

$$("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    $$("[data-filter]").forEach((item) =>
      item.setAttribute("aria-pressed", String(item === button)),
    );
    // A hidden selection is cleared so operators cannot confirm a vehicle outside the active filter.
    if (
      state.selected &&
      state.filter !== "all" &&
      state.selected.owner_type !== state.filter
    )
      selectCandidate(null);
    renderCandidates();
  }),
);
$("#openConfirm").addEventListener("click", () => {
  if (!state.selected || state.confirmed) return;
  $("#confirmError").hidden = true;
  $("#confirmDetails").innerHTML =
    `<strong>${esc(state.selected.vehicle_id)} ${ownerBadge(state.selected.owner_type)}</strong>${esc(state.result.order.pickup_rep)} → ${esc(state.result.order.dropoff_rep)}<br>상차 ${esc(dateTime(state.result.order.order_time))}<br>${esc(state.result.order.container_type)} · ${number(state.result.order.weight_kg)} kg${state.result.gate.status === "WARN" ? `<p class="alert alert-warning compact">${esc(state.result.gate.message)}</p>` : ""}`;
  $("#confirmDialog").showModal();
  $("#cancelConfirm").focus();
});
$("#cancelConfirm").addEventListener("click", () =>
  $("#confirmDialog").close(),
);
$("#confirmDialog").addEventListener("cancel", (event) => {
  if ($("#confirmDispatch").disabled) event.preventDefault();
});
$("#confirmDispatch").addEventListener("click", async () => {
  if (!state.selected || state.confirmed || $("#confirmDispatch").disabled)
    return;
  const button = $("#confirmDispatch");
  button.disabled = true;
  button.textContent = "확정 처리 중…";
  $("#cancelConfirm").disabled = true;
  $(".dialog-close").disabled = true;
  try {
    const data = await api("/api/dispatch", {
      method: "POST",
      body: JSON.stringify({
        vehicle_id: state.selected.vehicle_id,
        order: state.order,
      }),
    });
    $("#confirmDialog").close();
    showSuccess(data.commit);
    toast("배차가 확정되었습니다.");
  } catch (error) {
    // A lost HTTP response can still mean a successful server commit.
    const persisted = await api(
      `/api/orders/${encodeURIComponent(state.order.order_id)}`,
    ).catch(() => null);
    if (persisted?.commit) {
      $("#confirmDialog").close();
      showSuccess(persisted.commit);
      return;
    }
    $("#confirmError").textContent =
      `${errorText(error)} 운송 정보 수정으로 돌아가 다시 조회할 수 있습니다.`;
    $("#confirmError").hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "배차 확정";
    $("#cancelConfirm").disabled = false;
    $(".dialog-close").disabled = false;
  }
});

function showSuccess(commit) {
  state.confirmed = true;
  $("#loadingState").hidden = true;
  $("#resultContent").hidden = true;
  $("#warningBanner").hidden = commit.gate_status !== "WARN";
  if (commit.gate_status === "WARN")
    $("#warningText").textContent =
      "확정된 운송건은 중량 경고 대상입니다. 운송 전 적재 중량을 확인해주세요.";
  $("#successDetails").innerHTML =
    `<dl>${detail("운송건 번호", commit.order_id)}${detail("배차 차량", `${commit.vehicle_id} · ${commit.owner_type}`)}${detail("운송 구간", `${commit.pickup_rep} → ${commit.dropoff_rep}`)}${detail("상차 예정", dateTime(commit.order_time))}${detail("운송 완료 예정", dateTime(commit.finish_time))}${detail("컨테이너 / 화물", `${commit.container_type} / ${number(commit.weight_kg)} kg`)}</dl>`;
  $("#successState").hidden = false;
  $("#sidebarFinalStep").classList.add("current");
  $(".results-heading").hidden = true;
  $("#successState").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadResult() {
  if (!state.order?.pickup || !state.order?.work_time) {
    $("#loadingState").hidden = true;
    $("#pageError").hidden = false;
    $("#pageError").innerHTML =
      '조회할 운송건이 없습니다. <a href="/" class="text-button">신규 운송건 입력으로 이동 →</a>';
    return;
  }
  try {
    if (state.order.order_id) {
      const previous = await api(
        `/api/orders/${encodeURIComponent(state.order.order_id)}`,
      );
      if (previous.commit) {
        showSuccess(previous.commit);
        return;
      }
    }
    if (!state.order.container_type) {
      throw new Error("지정 컨테이너 타입을 선택한 뒤 다시 조회해주세요.");
    }
    const [context, result] = await Promise.all([
      api(`/api/bootstrap?at=${encodeURIComponent(state.order.work_time)}`),
      api("/api/recommend", {
        method: "POST",
        body: JSON.stringify(state.order),
      }),
    ]);
    state.order.order_id = result.order_id;
    saveDraft(state.order);
    if (result.status === "BLOCK") throw new Error(result.gate.message);
    state.result = result;
    renderSummary(result);
    $("#loadingState").hidden = true;
    $("#resultContent").hidden = false;
    state.map = new RouteView("routeMap", context.coordinates);
    renderCandidates();
    // Preview the first candidate, but confirmation always requires the explicit confirm dialog.
    selectCandidate(result.candidates[0]?.vehicle_id || null);
    $("#fitRoute").addEventListener("click", () => state.map.fit());
    $("#retryMap").addEventListener("click", () => state.map.retry());
  } catch (error) {
    $("#loadingState").hidden = true;
    $("#pageError").textContent = errorText(error);
    $("#pageError").hidden = false;
    const link = document.createElement("a");
    link.href = "/?edit=1";
    link.className = "text-button";
    link.textContent = "운송 정보 수정 →";
    $("#pageError").append(link);
  }
}
loadResult();
// Revalidate when a browser restores this page from its Back/forward cache.
window.addEventListener("pageshow", (event) => {
  if (event.persisted) location.reload();
});





