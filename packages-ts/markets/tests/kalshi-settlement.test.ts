import { describe, expect, it } from "vitest";

import { kalshiSettlementFor } from "../src/kalshi-settlement.js";
import { ContractIdError } from "../src/resolvers/kalshi-nhigh.js";

describe("kalshiSettlementFor", () => {
  it("dispatches KHIGH* to the NHIGH resolver", () => {
    const r = kalshiSettlementFor("KHIGHNYC", "2025-01-06");
    expect(r.settlementSource).toBe("cli.archive");
    expect(r.settlementStation).toBe("KNYC");
    expect(r.cityTicker).toBe("NYC");
    expect(r.contractDate).toBe("2025-01-06");
  });

  it("dispatches KLOW* to the NLOW resolver", () => {
    const r = kalshiSettlementFor("KLOWNYC", "2025-01-06");
    expect(r.settlementSource).toBe("cli.archive");
    expect(r.settlementStation).toBe("KNYC");
  });

  it("upper-cases the contract id", () => {
    const r = kalshiSettlementFor("khighnyc", "2025-01-06");
    expect(r.settlementStation).toBe("KNYC");
  });

  it("throws ContractIdError on empty input", () => {
    expect(() => kalshiSettlementFor("", "2025-01-06")).toThrow(ContractIdError);
  });

  it("throws ContractIdError when the prefix isn't KHIGH or KLOW", () => {
    expect(() => kalshiSettlementFor("FOOBAR", "2025-01-06")).toThrow(ContractIdError);
    expect(() => kalshiSettlementFor("NHIGHNYC", "2025-01-06")).toThrow(ContractIdError);
  });
});
