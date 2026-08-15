import { Link } from 'react-router-dom';
import { Snowfall } from '../components/Snowfall';
import '../components/ErrorPage.css';

export function NotFoundPage() {
  return (
    <div className="error-page">
      <Snowfall />
      <div className="error-page-content">
        <p className="error-page-eyebrow">404</p>
        <h1 className="error-page-title">Did you get lost in a blizzard?</h1>
        <p className="error-page-subtitle">
          This page melted away, moved, or never existed in the first place. Let's dig you out and
          get you back to solid ground.
        </p>
        <div className="error-page-actions">
          <Link to="/" className="btn btn-primary">
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
