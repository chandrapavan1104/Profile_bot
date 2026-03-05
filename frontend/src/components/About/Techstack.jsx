import React from "react";
import { Col, Row } from "react-bootstrap";
import portfolio from "../../Portfolio";

function Techstack() {
  const skillCategories = [
    "languages",
    "frontend",
    "backend",
    "databases",
    "cloudDevops",
    "aiMl",
    "others",
  ];

  const skills =
    skillCategories
      .flatMap((key) => portfolio.skills?.[key] || [])
      .filter((skill) => typeof skill === "string" && skill.trim().length) || [];

  return (
    <Row style={{ justifyContent: "center", paddingBottom: "50px" }}>
      {skills.map((skill) => (
        <Col xs={6} md={3} className="tech-icons" key={skill}>
          <div className="tech-icons-text">{skill}</div>
        </Col>
      ))}
    </Row>
  );
}

export default Techstack;
