import React, { useState, useEffect, useMemo } from "react";
import { Container, Row } from "react-bootstrap";
import Button from "react-bootstrap/Button";
import Particle from "../Particle";
import { AiOutlineDownload } from "react-icons/ai";
import { Document, Page, pdfjs } from "react-pdf";
import portfolio from "../../Portfolio";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import localResume from "../../Assets/Chandra.pdf";

pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

function ResumeNew() {
  const [width, setWidth] = useState(1200);

  const { previewSource, downloadLink, canPreviewPdf } = useMemo(() => {
    const remoteLink = portfolio.resumeLink;
    const hasRemotePdf =
      typeof remoteLink === "string" && remoteLink.toLowerCase().endsWith(".pdf");

    return {
      previewSource: hasRemotePdf ? remoteLink : localResume,
      downloadLink: localResume,
      canPreviewPdf: Boolean(hasRemotePdf ? remoteLink : localResume),
    };
  }, []);

  useEffect(() => {
    setWidth(window.innerWidth);
  }, []);

  return (
    <div>
      <Container fluid className="resume-section">
        <Particle />
        <Row style={{ justifyContent: "center", position: "relative" }}>
          <Button
            variant="primary"
            href={downloadLink}
            target="_blank"
            rel="noreferrer"
            style={{ maxWidth: "250px" }}
          >
            <AiOutlineDownload />
            &nbsp;Download CV
          </Button>
        </Row>

        {canPreviewPdf ? (
          <Row className="resume">
            <Document file={previewSource} className="d-flex justify-content-center">
              <Page pageNumber={1} scale={width > 786 ? 1.7 : 0.6} />
            </Document>
          </Row>
        ) : (
          <Row className="resume">
            <p style={{ color: "white", textAlign: "center" }}>
              The resume opens in a new tab.
            </p>
          </Row>
        )}
      </Container>
    </div>
  );
}

export default ResumeNew;
