import React from "react";
import Typewriter from "typewriter-effect";
import portfolio from "../../Portfolio";

function Type() {
  const highlights = [
    "Full-Stack Engineer",
    "GenAI Developer",
    "Eat.",
    "Code.",
    "Sleep.",
    "Repeat.",
  ]
    .filter(Boolean)
    .filter((value, index, self) => self.indexOf(value) === index);

  return (
    <Typewriter
      options={{
        strings: highlights.length ? highlights : ["Developer"],
        autoStart: true,
        loop: true,
        deleteSpeed: 50,
      }}
    />
  );
}

export default Type;
