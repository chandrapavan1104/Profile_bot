import React from "react";
import Card from "react-bootstrap/Card";
import { ImPointRight } from "react-icons/im";
import portfolio from "../../Portfolio";

function AboutCard() {
  const currentRole = portfolio.experience?.[0];
  const topEducation = portfolio.education?.[0];
  const focusAreas = ["Full-Stack Development", "GenAI Development", "Problem Solving -  DSA"];

  return (
    <Card className="quote-card-view">
      <Card.Body>
        <blockquote className="blockquote mb-0">
          <p style={{ textAlign: "justify" }}>
            Hi everyone! I’m{" "}
            <span className="purple">{portfolio.name}</span> from{" "}
            <span className="purple">{portfolio.location}</span>.
            <br />
            {currentRole && (
              <>
                I’m currently working as a{" "}
                <span className="purple">{currentRole.title}</span> at{" "}
                <span className="purple">{currentRole.company}</span>.
                <br />
              </>
            )}
            {topEducation && (
              <>
                I completed my{" "}
                <span className="purple">{topEducation.degree}</span> at{" "}
                <span className="purple">{topEducation.institution}</span>.
              </>
            )}
            <br />
            <br />
            Some focus areas that keep me energized:
          </p>

          <ul>
            {focusAreas.map((area) => (
              <li className="about-activity" key={area}>
                <ImPointRight /> {area}
              </li>
            ))}
          </ul>

          <p style={{ color: "rgb(155 126 172)" }}>
            "Strive to build things that make a difference!"
          </p>
          <footer className="blockquote-footer">
            {portfolio.name?.split(" ")[0] || "Portfolio"}
          </footer>
        </blockquote>
      </Card.Body>
    </Card>
  );
}

export default AboutCard;
