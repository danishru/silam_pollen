import React, { useEffect, useMemo, useState } from "react";

const INTEGRATION_DOMAIN = "silam_pollen";
const ANALYTICS_URL = "https://analytics.home-assistant.io/custom_integrations.json";
const RELEASES_URL = "https://api.github.com/repos/danishru/silam_pollen/releases?per_page=100";
const RELEASE_BASE_URL = "https://github.com/danishru/silam_pollen/releases/tag";

function normalizeVersion(version) {
  return String(version || "").trim().replace(/^v/i, "");
}

function compareVersionsDesc(a, b) {
  const left = normalizeVersion(a).split(/[\.-]/);
  const right = normalizeVersion(b).split(/[\.-]/);

  const len = Math.max(left.length, right.length);
  for (let i = 0; i < len; i += 1) {
    const av = left[i] ?? "";
    const bv = right[i] ?? "";

    const an = Number(av);
    const bn = Number(bv);

    if (Number.isFinite(an) && Number.isFinite(bn) && an !== bn) {
      return bn - an;
    }

    if (av !== bv) {
      return bv.localeCompare(av);
    }
  }

  return 0;
}

function formatNumber(value) {
  if (value === null || value === undefined) {
    return "—";
  }

  return new Intl.NumberFormat().format(value);
}

export default function SilamPollenStats() {
  const [analytics, setAnalytics] = useState(null);
  const [releases, setReleases] = useState([]);
  const [error, setError] = useState(null);
  const [loadedAt, setLoadedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadStats() {
      try {
        const [analyticsResponse, releasesResponse] = await Promise.all([
          fetch(ANALYTICS_URL),
          fetch(RELEASES_URL),
        ]);

        if (!analyticsResponse.ok) {
          throw new Error(`Home Assistant Analytics returned HTTP ${analyticsResponse.status}`);
        }

        if (!releasesResponse.ok) {
          throw new Error(`GitHub Releases API returned HTTP ${releasesResponse.status}`);
        }

        const analyticsJson = await analyticsResponse.json();
        const releasesJson = await releasesResponse.json();

        if (!cancelled) {
          setAnalytics(analyticsJson);
          setReleases(Array.isArray(releasesJson) ? releasesJson : []);
          setLoadedAt(new Date());
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || String(err));
        }
      }
    }

    loadStats();

    return () => {
      cancelled = true;
    };
  }, []);

  const rows = useMemo(() => {
    const integration = analytics?.[INTEGRATION_DOMAIN];
    const versions = integration?.versions ?? {};

    const releasesByVersion = new Map(
      releases.map((release) => [
        normalizeVersion(release.tag_name),
        {
          tagName: release.tag_name,
          url: release.html_url,
          prerelease: release.prerelease,
          downloads: Array.isArray(release.assets)
            ? release.assets.reduce((sum, asset) => sum + (asset.download_count || 0), 0)
            : 0,
        },
      ])
    );

    return Object.entries(versions)
      .map(([version, installs]) => {
        const normalized = normalizeVersion(version);
        const release = releasesByVersion.get(normalized);

        return {
          version,
          installs: Number(installs) || 0,
          downloads: release?.downloads ?? null,
          releaseUrl: release?.url ?? `${RELEASE_BASE_URL}/v${normalized}`,
          releaseLabel: release?.tagName ?? `v${normalized}`,
          prerelease: release?.prerelease ?? false,
        };
      })
      .sort((a, b) => compareVersionsDesc(a.version, b.version));
  }, [analytics, releases]);

  const totalInstalls = analytics?.[INTEGRATION_DOMAIN]?.total ?? null;
  const totalDownloads = releases.reduce(
    (sum, release) =>
      sum +
      (Array.isArray(release.assets)
        ? release.assets.reduce((assetSum, asset) => assetSum + (asset.download_count || 0), 0)
        : 0),
    0
  );

  if (error) {
    return (
      <div className="silamStats silamStatsError">
        Failed to load statistics: {error}
      </div>
    );
  }

  if (!analytics) {
    return <div className="silamStats">Loading SILAM Pollen statistics…</div>;
  }

  return (
    <div className="silamStats">
      <div className="silamStatsSummary">
        <div>
          <strong>{formatNumber(totalInstalls)}</strong>
          <span>active reported installations</span>
        </div>
        <div>
          <strong>{formatNumber(totalDownloads)}</strong>
          <span>GitHub release asset downloads</span>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Version</th>
            <th>Reported installations</th>
            <th>GitHub downloads</th>
            <th>Release</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.version}>
              <td>
                <code>{row.version}</code>
                {row.prerelease ? <span className="silamStatsBadge">pre-release</span> : null}
              </td>
              <td>{formatNumber(row.installs)}</td>
              <td>{formatNumber(row.downloads)}</td>
              <td>
                <a href={row.releaseUrl} target="_blank" rel="noreferrer">
                  {row.releaseLabel}
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="silamStatsNote">
        Home Assistant Analytics is opt-in and shows only aggregated, anonymized reported installations.
        GitHub downloads count release assets only and may not match active installations.
        {loadedAt ? ` Updated in browser: ${loadedAt.toLocaleString()}.` : ""}
      </p>
    </div>
  );
}