/**
 * k6 부하 테스트 — MAU 1,000 기준 피크 100 VU
 * 통과 기준: p99 ≤ 500ms, 에러율 < 1%
 *
 * 실행:
 *   docker run --rm -i --network host grafana/k6 run - < scripts/load-test.js
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate } from "k6/metrics";

const errorRate = new Rate("errors");

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  stages: [
    { duration: "30s", target: 30 },   // 램프업
    { duration: "1m", target: 30 },    // 워밍업
    { duration: "30s", target: 100 },  // 피크 램프업
    { duration: "2m", target: 100 },   // 피크 유지
    { duration: "30s", target: 0 },    // 램프다운
  ],
  thresholds: {
    http_req_duration: ["p(99)<500"],  // p99 ≤ 500ms
    http_req_failed: ["rate<0.01"],    // 에러율 < 1%
    errors: ["rate<0.01"],
  },
};

/**
 * 트래픽 가중치에 따라 시나리오 선택
 * feed 60% / news 25% / early 10% / health 5%
 */
function pickScenario() {
  const r = Math.random();
  if (r < 0.60) return "feed";
  if (r < 0.85) return "news";
  if (r < 0.95) return "early";
  return "health";
}

export default function () {
  const scenario = pickScenario();
  let res;

  switch (scenario) {
    case "feed":
      res = http.get(`${BASE_URL}/api/v1/trends?locale=ko`, {
        tags: { name: "feed" },
      });
      check(res, {
        "feed 200": (r) => r.status === 200,
      }) || errorRate.add(1);
      break;

    case "news":
      res = http.get(`${BASE_URL}/api/v1/news?locale=ko`, {
        tags: { name: "news" },
      });
      check(res, {
        "news 200": (r) => r.status === 200,
      }) || errorRate.add(1);
      break;

    case "early":
      res = http.get(`${BASE_URL}/api/v1/trends/early?locale=ko`, {
        tags: { name: "early" },
        // 401 is expected for unauthenticated requests — don't count as http_req_failed
        responseCallback: http.expectedStatuses({ min: 200, max: 499 }),
      });
      check(res, {
        "early <500": (r) => r.status < 500,
      }) || errorRate.add(1);
      break;

    case "health":
    default:
      res = http.get(`${BASE_URL}/health`, {
        tags: { name: "health" },
      });
      check(res, {
        "health 200": (r) => r.status === 200,
      }) || errorRate.add(1);
      break;
  }

  sleep(1);
}
