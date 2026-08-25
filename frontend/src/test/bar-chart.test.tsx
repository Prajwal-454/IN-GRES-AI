import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import BarChart from "@/components/BarChart";

describe("BarChart", () => {
  it("renders bars with labels and values", () => {
    render(
      <BarChart
        data={[
          { label: "Safe", value: 4 },
          { label: "Critical", value: 1 },
        ]}
      />
    );
    expect(screen.getByText("Safe")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders an empty container for empty data", () => {
    const { container } = render(<BarChart data={[]} />);
    expect(container.firstChild).toBeEmptyDOMElement();
  });
});