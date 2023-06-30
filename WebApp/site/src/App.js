import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import HomePage from './guest/views/HomePage';
import SecurityPolicy from './guest/views/SecurityPolicy';
import Contact from './guest/views/Contact';
import './App.css';
import Dashboard from './client/dashboard';

export default function App() {
  return (
    <Router>
      <div id="app">
        <header>
          <div className="header-style">
            <div className="logo-container">
              <img
                className="logo"
                src="./RPS.png"
                alt="Logo de HackFactorizz"
              />
            </div>
            <div className="text-container">
              <h1 className="title">HackFactorizz</h1>
              <h3 className="slogan">Protection optimale contre les ransomwares</h3>
            </div>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/security-policy" element={<SecurityPolicy />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>

        <footer>
          <div className="footerbar">
            <ul>
              <li>&copy; 2023 Application Anti-Ransomware. Tous droits réservés.</li>
              <br />
              <li>
                <a href="/security-policy">Politique de sécurité</a>
              </li>
              <br />
              <li>
                <a href="/contact">Contactez-nous</a>
              </li>
            </ul>
          </div>
        </footer>
      </div>
    </Router>
  );
}
