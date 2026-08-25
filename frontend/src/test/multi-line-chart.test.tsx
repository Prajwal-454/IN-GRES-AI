import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MultiLineChart from "@/components/MultiLineChart";

describe("MultiLineChart", () => {
  it("renders series labels in the legend", () => {
    render(
      <MultiLineChart
        series={[
          {
            label: "Telangana",
            color: "#0f766e",
            points: [
              { label: "2017", value: 70 },
              { label: "2018", value: 74 },
            ],
          },
          {
            label: "Karnataka",
            color: "#b91c1c",
            points: [
              { label: "2017", value: 60 },
              { label: "2018", value: 63 },
            ],
          },
        ]}
      />
    );
    expect(screen.getByText("Telangana")).toBeInTheDocument();
    expect(screen.getByText("Karnataka")).toBeInTheDocument();
    expect(screen.getByRole("img")).toBeInTheDocument();
  });

  it("renders nothing when every series is empty", () => {
    const { container } = render(
      <MultiLineChart
        series={[
          { label: "A", color: "#0f766e", points: [] },
          { label: "B", color: "#b91c1c", points: [] },
        ]}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
