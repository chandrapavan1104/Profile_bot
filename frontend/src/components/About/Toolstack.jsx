import React from "react";
import { Col, Row } from "react-bootstrap";
import portfolio from "../../Portfolio";

function Toolstack() {
  const tools = portfolio.skills?.tools || [];

  return (
    <Row style={{ justifyContent: "center", paddingBottom: "50px" }}>
      {tools.map((tool) => (
        <Col xs={6} md={3} className="tech-icons" key={tool}>
          <div className="tech-icons-text">{tool}</div>
        </Col>
      ))}
    </Row>
  );
}

export default Toolstack;
