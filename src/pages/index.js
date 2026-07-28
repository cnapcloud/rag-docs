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
          사내 문서를 AI가 검색 가능한 지식으로
          <br />
          셀프호스팅 RAG&nbsp;Platform
        </Heading>
        <p className={clsx('hero__subtitle', styles.heroSubtitle)}>
          검색부터 접근 제어, 중복 문서 처리, MCP 에이전트 연동, 관리 콘솔까지 하나로 완결되는
          RAG 인프라를 제공합니다.
        </p>
        <div className={styles.buttons}>
          <Link className="button button--primary button--lg" to="/overview/introduction">
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
