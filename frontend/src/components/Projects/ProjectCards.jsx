import React from "react";
import Card from "react-bootstrap/Card";
import Button from "react-bootstrap/Button";
import { CgWebsite } from "react-icons/cg";
import { BsGithub } from "react-icons/bs";

function ProjectCards(props) {
  const { imgPath, title, description, ghLink, demoLink, techStack, isBlog } =
    props;

  return (
    <Card className="project-card-view">
      {imgPath && <Card.Img variant="top" src={imgPath} alt={`${title} cover`} />}
      <Card.Body>
        <Card.Title>{title}</Card.Title>
        <Card.Text style={{ textAlign: "justify" }}>
          {description}
        </Card.Text>
        {Array.isArray(techStack) && techStack.length > 0 && (
          <div className="d-flex flex-wrap" style={{ gap: "0.5rem" }}>
            {techStack.map((tech) => (
              <span className="badge bg-secondary" key={tech}>
                {tech}
              </span>
            ))}
          </div>
        )}
        {ghLink && (
          <Button
            variant="primary"
            href={ghLink}
            target="_blank"
            rel="noreferrer"
            style={{ marginTop: "15px" }}
          >
            <BsGithub /> &nbsp;
            {isBlog ? "Blog" : "GitHub"}
          </Button>
        )}
        {!isBlog && demoLink && (
          <Button
            variant="primary"
            href={demoLink}
            target="_blank"
            rel="noreferrer"
            style={{
              marginLeft: ghLink ? "10px" : "0",
              marginTop: "15px",
            }}
          >
            <CgWebsite /> &nbsp;
            {"Demo"}
          </Button>
        )}
      </Card.Body>
    </Card>
  );
}

export default ProjectCards;
