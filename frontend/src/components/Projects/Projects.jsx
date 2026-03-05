import React from "react";
import { Container, Row, Col } from "react-bootstrap";
import ProjectCard from "./ProjectCards";
import Particle from "../Particle";
import portfolio from "../../Portfolio";

function Projects() {
  const projects = portfolio.projects || [];

  return (
    <Container fluid className="project-section">
      <Particle />
      <Container>
        <h1 className="project-heading">
          My Recent <strong className="purple">Works </strong>
        </h1>
        <p style={{ color: "white" }}>
          Here are a few projects I&apos;ve worked on recently.
        </p>
        <Row style={{ justifyContent: "center", paddingBottom: "10px" }}>
          {projects.length === 0 && (
            <Col md={8} style={{ color: "white", textAlign: "center" }}>
              New projects coming soon. Stay tuned!
            </Col>
          )}
          {projects.map((project) => (
            <Col md={4} className="project-card" key={project.name}>
              <ProjectCard
                imgPath={project.image}
                isBlog={false}
                title={project.name}
                description={project.description}
                ghLink={project.github}
                demoLink={project.demo}
                techStack={project.techStack}
              />
            </Col>
          ))}
        </Row>
      </Container>
    </Container>
  );
}

export default Projects;
