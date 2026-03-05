import React, { useEffect, useState } from "react";
import GitHubCalendar from "react-github-calendar";
import { Row } from "react-bootstrap";
import portfolio from "../../Portfolio";

function Github() {
  const githubUrl = portfolio.socialLinks?.github;
  const username = githubUrl ? githubUrl.split("/").filter(Boolean).pop() : null;
  const [calendarConfig, setCalendarConfig] = useState({
    blockSize: 24,
    blockMargin: 6,
    fontSize: 16,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const computeConfig = () => {
      const width = window.innerWidth;

      if (width < 480) {
        return { blockSize: 9, blockMargin: 2, fontSize: 11 };
      }
      if (width < 768) {
        return { blockSize: 12, blockMargin: 3, fontSize: 12 };
      }
      if (width < 1024) {
        return { blockSize: 16, blockMargin: 4, fontSize: 14 };
      }
      return { blockSize: 24, blockMargin: 6, fontSize: 16 };
    };

    const updateConfig = () => setCalendarConfig(computeConfig());
    updateConfig();

    window.addEventListener("resize", updateConfig);
    return () => window.removeEventListener("resize", updateConfig);
  }, []);

  if (!username) {
    return null;
  }

  return (
    <Row
      style={{
        justifyContent: "center",
        paddingBottom: "10px",
        color: "white",
      }}
    >
      <h1 className="project-heading pb-4" style={{ paddingBottom: "20px" }}>
        Days I <strong className="purple">Code</strong>
      </h1>
      <div className="github-calendar-wrapper">
        <GitHubCalendar
          username={username}
          blockSize={calendarConfig.blockSize}
          blockMargin={calendarConfig.blockMargin}
          color="#c084f5"
          fontSize={calendarConfig.fontSize}
          showWeekdayLabels
          hideColorLegend
          hideTotalCount
        />
      </div>
      <div className="github-calendar-legend">
        <span className="legend-label">Less</span>
        <div className="legend-bar">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </div>
        <span className="legend-label">More</span>
      </div>
    </Row>
  );
}

export default Github;
