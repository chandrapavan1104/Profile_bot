// portfolio.js
const portfolio = {
    // =======================
    // 🔹 Personal Information
    // =======================
    name: "Chandra Pavan Reddy Chada",
    title: "Full-Stack Engineer | GenAI Developer",
    subTitle:
      "Half logic, half caffeine, but fully committed to making weird ideas real.",
    email: "chandrapavanreddy@gmail.com",
    phone: "+1 (669) 369-9147",
    location: "San Jose, California, USA",
    resumeLink: "https://github.com/chandrapavan1104", // optional direct resume or GitHub link
    socialLinks: {
      linkedin: "https://linkedin.com/in/chandra-pavan",
      github: "https://github.com/chandrapavan1104",
    },
  
    // =======================
    // 🔹 Skills
    // =======================
    skills: {
      languages: ["Python", "Java", "C/C++", "JavaScript", "TypeScript", "SQL"],
      frontend: [
        "React",
        "Next.js",
        "Angular",
        "Tailwind CSS",
        "Bootstrap",
        "Redux",
        "HTML5",
        "CSS3",
        "SCSS/LESS",
      ],
      backend: ["Node.js", "Express.js", "Flask", "FastAPI", "Spring Boot"],
      databases: ["PostgreSQL", "MongoDB", "MySQL", "Amazon RDS"],
      cloudDevops: [
        "AWS (EC2, S3, RDS, Lambda, ELB)",
        "Docker",
        "Jenkins",
        "Kubernetes",
        "CI/CD",
      ],
      aiMl: [
        "PyTorch",
        "TensorFlow",
        "LangChain",
        "RAG",
        "Hugging Face",
        "Whisper",
        "Llama-3.3-70B",
      ],
      tools: [
        "Git",
        "JIRA",
        "Postman",
        "BrowserStack",
        "VSCode",
        "Cursor",
        "Windsurf",
      ],
      others: ["REST APIs", "GraphQL", "Kafka", "Redis", "Microservices"],
    },
  
    // =======================
    // 🔹 Education
    // =======================
    education: [
      {
        degree: "Master of Science in Software Engineering",
        institution: "San Jose State University, California, USA",
        duration: "Jan 2022 – Dec 2023",
      },
      {
        degree: "Bachelor of Technology in Computer Science",
        institution: "VNR Vignana Jyothi Institute of Engineering and Technology, Hyderabad, India",
        duration: "July 2017 – May 2021",
      },
    ],
  
    // =======================
    // 🔹 Experience
    // =======================
    experience: [
      {
        title: "Full-Stack Engineer",
        company: "Xnode.ai",
        duration: "July 2024 – Present",
        details: [
          "At Xnode, I contributed to building advanced GenAI-powered features by integrating large language models (LLMs) into our platform.",
          "I worked on projects like file summarization, navigation bots, and a voice agent interface, focusing on clean, modular architecture and scalable design. ",
          "I used tools like Whisper, LangChain, and vector databases to implement multimodal workflows and retrieval-augmented generation (RAG). ",
          "My role spanned both frontend and backend, ensuring smooth user experiences and high system reliability.",
        ],
      },
      {
        title: "Software Engineer",
        company: "Oriana Software Solutions",
        duration: "Aug 2023 – July 2024",
        details: [
          "Developed REST APIs with FastAPI backend and React frontend using Redux and Tailwind CSS.",
          "Implemented JWT authentication and built fault-tolerant API communication.",
        ],
      },
      {
        title: "Software Developer",
        company: "VirtuTech Solutions",
        duration: "Jan 2020 – Jan 2022",
        details: [
          "Developed e-commerce and logistics apps using React, TypeScript, and Node.js.",
          "Automated CI/CD with AWS CodePipeline and Docker, reducing deployment time by 40%.",
        ],
      },
    ],
  
    // =======================
    // 🔹 Projects
    // =======================
    projects: [
      {
        name: "Kirana.ai",
        techStack: [
          "Next.js",
          "TailwindCSS",
          "Python",
          "FastAPI",
          "Whisper",
          "Llama-3.3-70B",
          "Phidata",
        ],
        description:
          "A Gen-AI voice-activated inventory management system for Kirana shops. Integrated Whisper for multilingual transcription and Llama-3.3-70B for NLP workflows on Groq Cloud. Enables natural voice commands to add, update, and retrieve inventory.",
        github: "https://github.com/chandrapavan1104/Kirana.ai",
        demo: "", // optional demo link if deployed
      },
      {
        name: "Profile Bot",
        techStack: [
          "LangChain",
          "ChromaDB",
          "FastAPI",
          "GCP Cloud Run",
          "GCS",
          "OpenAI API",
        ],
        description:
          "AI chatbot that answers questions about my profile and experience. Uses vector database for context retrieval and LangChain for reasoning. Deployed on GCP with dynamic document ingestion.",
        github: "https://github.com/chandrapavan1104/Profile_bot",
        demo: "",
      },
      {
        name: "Flight Finder",
        techStack: ["React.js", "Flask", "REST API", "OpenSky API"],
        description:
          "AI-enabled flight search tool integrating OpenSky APIs to fetch and visualize real-time flight data with smart filtering.",
        github: "https://github.com/chandrapavan1104/FlightFinder",
        demo: "",
      },
      {
        name: "RBAC Management System",
        techStack: ["Angular", "Node.js", "Express", "PostgreSQL", "AWS RDS"],
        description:
          "SaaS-based Role-Based Access Control platform with six-level permission granularity. Includes JWT authentication, real-time role updates, and Angular UI for visualization. Reduced access management time by 40%.",
        github: "https://github.com/chandrapavan1104/RBAC",
        demo: "",
      },
      {
        name: "ChessMaster",
        techStack: ["Next.js", "TailwindCSS", "Python", "Flask", "Stockfish"],
        description:
          "Web-based chess application with AI move prediction using Stockfish. Deployed on AWS (EC2 & S3). Features include move analysis, dark mode, and interactive gameplay.",
        github: "https://github.com/chandrapavan1104/ChessMaster",
        demo: "",
      },
      {
        name: "Paint with C",
        techStack: ["Turbo C/C++"],
        description:
          "A graphics-based drawing program built using Turbo C/C++ with a 15-color palette and shape tools like line, ellipse, and rectangle. Introduced mouse interaction for freehand drawing and viewport management.",
        github: "https://github.com/chandrapavan1104/Wonders-with-C/blob/main/Paint_Tools_Final.CPP",
        demo: "",
      },
 
      {
        name: "Ecficio",
        techStack: ["React.js", "Node.js", "MongoDB", "Express", "AWS"],
        description:
          "Corporate management dashboard enabling admins to manage company workflows with real-time metrics and role-based access.",
        github: "https://github.com/chandrapavan1104/Ecficio",
        demo: "",
      },

      {
        name: "Fitnessclub",
        techStack: [
          "Angular CLI 9.1.5",
          "Node.js",
          "JavaScript",
          "TypeScript",
          "HTML",
          "SCSS",
          "Karma",
          "Protractor"
        ],
        description: "A MEAN stack web application designed for a Fitness Store. It features a full-stack architecture with an Angular front-end for a modern user experience and a Node.js/Express.js back-end for handling user accounts, fitness course listings, and other store functionalities.",
        github: "https://github.com/chandrapavan1104/Fitnessclub",
        demo: ""
      },
      {
        name: "Recipe_Store",
        techStack: [
          "React (JavaScript/CSS/HTML)",
          "Django (Python)",
          "Python",
          "JavaScript",
          "HTML",
          "CSS"
        ],
        description: "A full-stack web application for a Recipe Store, serving as a go-to platform for users to find and try new food recipes. It utilizes a React framework for the modern, dynamic front-end user interface and Django (Python-based) for the robust back-end.",
        github: "https://github.com/chandrapavan1104/Recipe_Store",
        demo: ""
      }
    ],
  
    // =======================
    // 🔹 About Me
    // =======================
    about:
      "Hi, I’m Chandra Pavan Reddy Chada, a passionate Full-Stack Engineer specializing in building scalable and intelligent web applications. I love integrating AI and automation into everyday products using technologies like React, Angular, Python, and Node.js. My work spans from creating GenAI-powered agents and RAG systems to designing efficient SaaS platforms and real-time dashboards. I believe in writing clean, maintainable code and constantly learning new tools that make technology more impactful." ,
    // =======================
    // 🔹 Contact Info
    // =======================
    contact: {
      email: "chandrapavanreddy@gmail.com",
      linkedin: "https://linkedin.com/in/chandra-pavan",
      github: "https://github.com/chandrapavan1104",
    },
  };
  
  export default portfolio;
