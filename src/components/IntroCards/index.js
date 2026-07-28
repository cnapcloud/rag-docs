import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const CardList = [
  {
    title: '처음 도입을 검토 중이신가요?',
    description: '제품 소개, 제품 구성, 차별점을 5분 안에 파악합니다.',
    linkLabel: '제품 개요 보기',
    to: '/overview/introduction',
  },
  {
    title: '지금 설치하시나요?',
    description: 'Docker Compose 기반으로 설치부터 인덱싱, 첫 검색까지 약 30분 만에 완료할 수 있습니다.',
    linkLabel: 'Quick Start 시작',
    to: '/getting-started/quickstart',
  },
  {
    title: '이미 운영 중이신가요?',
    description: 'k8s 배포의 백업·복구·업그레이드 runbook과 관측 구성을 확인합니다.',
    linkLabel: 'k8s Runbook 보기',
    to: '/deploy/runbook',
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
