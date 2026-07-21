import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import IntroCards from '@site/src/components/IntroCards';
import HomepageFeatures from '@site/src/components/HomepageFeatures';

import Heading from '@theme/Heading';
import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className={clsx('hero__title', styles.heroTitle)}>
          사내 문서를 검색 가능한 상태로 유지하는
          <br />
          셀프호스티드 RAG 검색 플랫폼
        </Heading>
        <p className={clsx('hero__subtitle', styles.heroSubtitle)}>
          {siteConfig.tagline} — 완전한 셀프호스팅, KB 단위 RBAC와 기업 SSO, 한국어 문서
          환경 특화, MCP를 통한 에이전트 연동까지 하나의 플랫폼에서 제공합니다.
        </p>
        <div className={styles.buttons}>
          <Link className="button button--primary button--lg" to="/overview">
            문서 시작하기 →
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <IntroCards />
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
