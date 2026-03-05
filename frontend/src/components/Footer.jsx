import React from "react";
import { Container, Row, Col } from "react-bootstrap";
import {
  AiFillGithub,
  AiOutlineTwitter,
  AiFillInstagram,
} from "react-icons/ai";
import { FaLinkedinIn } from "react-icons/fa";
import portfolio from "../Portfolio";

function Footer() {
  let date = new Date();
  let year = date.getFullYear();
  const socialLinks = portfolio.socialLinks || {};
  const SOCIAL_ICONS = {
    github: <AiFillGithub />,
    twitter: <AiOutlineTwitter />,
    instagram: <AiFillInstagram />,
    linkedin: <FaLinkedinIn />,
  };
  const initials = portfolio.name
    ? portfolio.name
        .split(" ")
        .map((chunk) => chunk[0])
        .join("")
        .toUpperCase()
    : "CP";

  return (
    <Container fluid className="footer">
      <Row>
        <Col md="4" className="footer-copywright">
          <h3>Designed and Developed by {portfolio.name}</h3>
        </Col>
        <Col md="4" className="footer-copywright">
          <h3>Copyright © {year} {initials}</h3>
        </Col>
        <Col md="4" className="footer-body">
          <ul className="footer-icons">
            {Object.entries(socialLinks)
              .filter(([network, url]) => SOCIAL_ICONS[network] && url)
              .map(([network, url]) => (
                <li className="social-icons" key={network}>
                  <a
                    href={url}
                    style={{ color: "white" }}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {SOCIAL_ICONS[network]}
                  </a>
                </li>
              ))}
          </ul>
        </Col>
      </Row>
    </Container>
  );
}

export default Footer;
