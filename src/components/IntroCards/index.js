import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const CardList = [
  {
    title: '처음 도입을 검토 중이신가요?',
    description: '제품 정의, 핵심 가치 제안, 3계층 구성(rag-api / rag-ent-api / rag-admin)을 5분 안에 파악합니다.',
    linkLabel: '제품 개요 보기',
    to: '/overview/01-product',
  },
  {
    title: '지금 설치하시나요?',
    description: 'docker-compose 기반 평가용 설치부터 첫 검색까지, 약 30분 만에 끝내는 Quick Start.',
    linkLabel: 'Quick Start 시작',
    to: '/install/02-quickstart',
  },
  {
    title: '이미 운영 중이신가요?',
    description: 'k8s 배포의 백업·복구·업그레이드 runbook과 관측 구성을 확인합니다.',
    linkLabel: 'k8s Runbook 보기',
    to: '/operations/01-runbook-k8s',
  },
];

function Card({title, description, linkLabel, to}) {
  return (
    <Link className={styles.card} to={to}>
      <Heading as="h3" className={styles.cardTitle}>
        {title}
      </Heading>
      <p className={styles.cardDescription}>{description}</p>
      <span className={styles.cardLink}>{linkLabel} →</span>
    </Link>
  );
}

export default function IntroCards() {
  return (
    <section className={styles.section}>
      <div className="container">
        <div className={styles.grid}>
          {CardList.map((props, idx) => (
            <Card key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
