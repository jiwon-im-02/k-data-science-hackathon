import { $, escapeHTML as esc } from "./common.js";

/**
 * Map rendering only. Road geometry never changes model distance, time or ranking.
 * Leaflet is local; OSM tiles and optional OSRM geometry require internet.
 * Only representative coordinates are sent, never vehicle IDs or cargo details.
 */
export class RouteView {
  constructor(elementId, coordinates) {
    this.coordinates = coordinates;
    this.version = 0;
    this.routeCache = new Map();
    this.last = null;
    this.bounds = null;
    if (!window.L) {
      $("#routeStatus").textContent =
        "지도 모듈을 불러오지 못했습니다. 아래 구간별 정보를 확인해주세요.";
      $("#tileNotice").hidden = false;
      $("#fitRoute").disabled = true;
      $("#retryMap").disabled = true;
      return;
    }
    this.map = L.map(elementId, {
      zoomControl: false,
      scrollWheelZoom: false,
      attributionControl: true,
    }).setView([36.0, 127.8], 7);
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    L.control
      .scale({ position: "bottomleft", imperial: false })
      .addTo(this.map);
    this.tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(this.map);
    this.tiles.on("tileerror", () => {
      $("#tileNotice").hidden = false;
    });
    this.tiles.on("tileload", () => {
      $("#tileNotice").hidden = true;
    });
    this.markers = L.layerGroup().addTo(this.map);
    this.lines = L.layerGroup().addTo(this.map);
    this.resizeObserver = new ResizeObserver(() => this.map.invalidateSize());
    this.resizeObserver.observe(document.getElementById(elementId));
  }
  latLng(coordinate) {
    if (
      !coordinate ||
      !Number.isFinite(coordinate.lat) ||
      !Number.isFinite(coordinate.lon)
    )
      return null;
    if (Math.abs(coordinate.lat) > 90 || Math.abs(coordinate.lon) > 180)
      return null;
    return [coordinate.lat, coordinate.lon];
  }
  marker(point, text, kind, label, permanent = false) {
    if (!point) return;
    const isVehicle = kind === "vehicle";
    const marker = L.marker(point, {
      icon: L.divIcon({
        className: "route-marker",
        html: `<span class="map-pin ${kind}">${esc(text)}</span>`,
        iconSize: [30, 35],
        iconAnchor: isVehicle ? [42, 15] : [15, 35],
      }),
      title: label,
      alt: label,
      zIndexOffset: isVehicle ? 900 : kind === "other" ? 0 : 500,
    }).addTo(this.markers);
    marker.bindTooltip(esc(label), {
      permanent,
      direction: isVehicle ? "left" : "top",
      offset: isVehicle ? [-35, -6] : [0, -35],
    });
  }
  async road(start, end) {
    if (start[0] === end[0] && start[1] === end[1])
      return { points: [start, end], road: true };
    const key = `${start[1]},${start[0]};${end[1]},${end[0]}`;
    if (this.routeCache.has(key)) return this.routeCache.get(key);
    const task = (async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(
          `https://router.project-osrm.org/route/v1/driving/${key}?overview=full&geometries=geojson&steps=false`,
          { signal: controller.signal },
        );
        if (!response.ok) throw new Error("route unavailable");
        const data = await response.json();
        const raw = data.routes?.[0]?.geometry?.coordinates;
        if (data.code !== "Ok" || !Array.isArray(raw) || raw.length < 2)
          throw new Error("no geometry");
        const points = raw.map((point) => [point[1], point[0]]);
        if (
          points.some(
            (point) => !Number.isFinite(point[0]) || !Number.isFinite(point[1]),
          )
        )
          throw new Error("invalid geometry");
        return { points, road: true };
      } catch {
        return { points: [start, end], road: false };
      } finally {
        clearTimeout(timeout);
      }
    })();
    this.routeCache.set(key, task);
    return task;
  }
  line(points, empty, road) {
    L.polyline(points, {
      color: "#ffffff",
      weight: 8,
      opacity: 0.85,
      interactive: false,
    }).addTo(this.lines);
    L.polyline(points, {
      color: empty ? "#ce8b49" : "#197c65",
      weight: empty ? 4 : 4.5,
      opacity: 0.95,
      dashArray: empty ? "8 7" : road ? null : "5 7",
      lineCap: "round",
    }).addTo(this.lines);
  }
  async show(result, vehicle) {
    this.last = { result, vehicle };
    if (!this.map) return;
    const version = ++this.version;
    this.markers.clearLayers();
    this.lines.clearLayers();
    const pickup = this.latLng(result.map?.pickup);
    const dropoff = this.latLng(result.map?.dropoff);
    const origin = vehicle
      ? this.latLng(this.coordinates[vehicle.available_location])
      : null;
    const visible = [pickup, dropoff, origin].filter(Boolean);
    this.bounds = visible.length ? L.latLngBounds(visible) : null;
    // Group equal coordinates instead of inventing different GPS positions.
    const groups = new Map();
    for (const candidate of result.candidates) {
      if (candidate.vehicle_id === vehicle?.vehicle_id) continue;
      const point = this.latLng(this.coordinates[candidate.current_location]);
      if (!point) continue;
      const key = point.join(",");
      if (!groups.has(key)) groups.set(key, { point, vehicles: [] });
      groups.get(key).vehicles.push(candidate);
    }
    for (const group of groups.values()) {
      const names = group.vehicles.map((c) => c.vehicle_id).join(", ");
      this.marker(
        group.point,
        group.vehicles.length > 1 ? String(group.vehicles.length) : "차",
        "other",
        `후보 차량: ${names}`,
      );
    }
    this.marker(
      pickup,
      "상",
      "pickup",
      `상차 · ${result.order.pickup_rep}`,
      true,
    );
    this.marker(
      dropoff,
      "하",
      "dropoff",
      `하차 · ${result.order.dropoff_rep}`,
      true,
    );
    if (origin)
      this.marker(
        origin,
        "차",
        "vehicle",
        `${vehicle.vehicle_id} · ${vehicle.available_location}`,
        true,
      );
    this.fit();
    const missing = !pickup || !dropoff || (vehicle && !origin);
    if (!pickup || !dropoff) {
      $("#routeStatus").textContent =
        "상·하차 거점 좌표가 없어 지도 경로를 표시할 수 없습니다. 운송 구간 정보를 확인해주세요.";
      return;
    }
    this.line([pickup, dropoff], false, false);
    if (origin) this.line([origin, pickup], true, false);
    $("#routeStatus").textContent =
      "도로 경로 조회 중 · 현재는 거점 간 연결선을 표시합니다.";
    const [loaded, empty] = await Promise.all([
      this.road(pickup, dropoff),
      origin ? this.road(origin, pickup) : Promise.resolve(null),
    ]);
    if (version !== this.version) return;
    this.lines.clearLayers();
    this.line(loaded.points, false, loaded.road);
    if (empty) this.line(empty.points, true, empty.road);
    this.bounds = L.latLngBounds([...loaded.points, ...(empty?.points || [])]);
    this.fit();
    if (missing)
      $("#routeStatus").textContent =
        "일부 차량 좌표 미등록 · 확인 가능한 구간만 표시합니다.";
    else if (!loaded.road || (empty && !empty.road))
      $("#routeStatus").textContent =
        "일부 도로 경로 조회 불가 · 해당 구간은 실제 도로가 아닌 거점 연결선입니다.";
    else
      $("#routeStatus").textContent =
        "OSRM 일반 도로 참고 경로 · 화물차 통행 제한·실시간 교통 미반영";
  }
  fit() {
    if (!this.map || !this.bounds) return;
    this.map.invalidateSize();
    this.map.fitBounds(this.bounds, {
      paddingTopLeft: [65, 70],
      paddingBottomRight: [65, 65],
      maxZoom: 12,
      animate: false,
    });
  }
  retry() {
    if (!this.map || !this.last) return;
    this.routeCache.clear();
    this.tiles.redraw();
    this.show(this.last.result, this.last.vehicle);
  }
}
